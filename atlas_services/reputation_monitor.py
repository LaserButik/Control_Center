# -*- coding: utf-8 -*-
"""ATLAS service: a light brand-reputation read via the Serper API.

Runs four plain searches for a brand (the brand, + review, + praise,
+ complaint), classifies each organic result as positive / negative /
neutral with a small English+Arabic keyword list, and deduplicates sources
by URL. Needs SERPER_API_KEY; without it, no network call is made.

Queries are plain phrases only: Serper rejects Google's grouping syntax
like ("a" OR "b") with HTTP 400.

CLI:
    python -m atlas_services.reputation_monitor --brand X --country ae --out path
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlsplit

try:
    import requests
except ImportError:
    requests = None

SERPER_URL = "https://google.serper.dev/search"
TIMEOUT_S = 15

POSITIVE = ("excellent", "great", "best", "recommend", "recommended",
            "trusted", "reliable", "professional", "praise", "love",
            "amazing", "top", "award", "ممتاز", "رائع", "أفضل", "موثوق",
            "احترافي", "مميز", "ننصح", "تميز")
NEGATIVE = ("scam", "fraud", "complaint", "complaints", "bad", "worst",
            "avoid", "terrible", "poor", "refund", "warning", "fake",
            "lawsuit", "احتيال", "نصب", "شكوى", "شكاوى", "سيئ", "تحذير",
            "مزيف", "رديء", "تجنب")


def _key() -> str:
    return (os.getenv("SERPER_API_KEY") or "").strip()


# The dedicated "<brand> complaint" query surfaces many results that NEGATE
# a negative word ("no complaints", "not a scam"). Those phrases are blanked
# out before matching, so they never count as negative on their own.
NEGATED = ("no complaints", "no complaint", "zero complaints",
           "without complaints", "never had a complaint",
           "not a scam", "is not a scam", "isn't a scam", "no scam",
           "not fake", "not bad",
           "لا توجد شكاوى", "بدون شكاوى", "لا شكاوى", "ليس نصب", "ليست نصب",
           "ليس احتيال", "ليست احتيال", "ليس سيئ")


def _classify(text: str) -> str:
    low = (text or "").lower()
    for phrase in NEGATED:
        low = low.replace(phrase, " ")
    pos = any(w in low for w in POSITIVE)
    neg = any(w in low for w in NEGATIVE)
    if pos and not neg:
        return "positive"
    if neg and not pos:
        return "negative"
    return "neutral"


def _default_poster(key: str):
    def _post(body):
        resp = requests.post(SERPER_URL, headers={"X-API-KEY": key,
                             "Content-Type": "application/json"},
                             json=body, timeout=TIMEOUT_S)
        return resp.status_code, (resp.json() if resp.content else {})
    return _post


def check_brand(brand: str, country: str = "ae", num: int = 20, *,
                poster=None) -> dict:
    brand = (brand or "").strip()
    if not brand:
        return {"ok": False, "reason": "invalid_brand"}
    key = _key()
    if not key:
        return {"ok": False, "reason": "serper_not_configured",
                "brand": brand}
    if poster is None and requests is None:
        return {"ok": False, "reason": "requests_not_installed",
                "brand": brand}
    post = poster or _default_poster(key)
    queries = ['"%s"' % brand, '"%s" review' % brand,
               '"%s" praise' % brand, '"%s" complaint' % brand]
    by_url, counts = {}, {"positive": 0, "negative": 0, "neutral": 0}
    for q in queries:
        try:
            status, data = post({"q": q, "gl": country,
                                 "num": max(1, min(int(num), 20))})
        except Exception as e:
            return {"ok": False, "reason": "request_failed:%s"
                    % type(e).__name__, "brand": brand}
        if not 200 <= int(status) < 300:
            return {"ok": False, "reason": "serper_http_%s" % status,
                    "brand": brand}
        for item in (data or {}).get("organic", []):
            url = item.get("link") or item.get("url") or ""
            if not url or url in by_url:
                continue
            title = item.get("title") or ""
            snippet = item.get("snippet") or ""
            sentiment = _classify(title + " " + snippet)
            counts[sentiment] += 1
            by_url[url] = {"title": title[:120], "url": url,
                           "snippet": snippet[:200], "sentiment": sentiment}
    sources = list(by_url.values())
    return {"ok": True, "brand": brand, "country": country,
            "total_mentions": len(sources),
            "unique_sources": len({urlsplit(s["url"]).hostname
                                   for s in sources}),
            "top_sources": sources[:10],
            "positive_hits": counts["positive"],
            "negative_hits": counts["negative"],
            "neutral_hits": counts["neutral"], "reason": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.reputation_monitor")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--country", default="ae")
    ap.add_argument("--num", type=int, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    r = check_brand(a.brand, a.country, a.num)
    if a.out and r.get("ok"):
        from pathlib import Path
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    sys.stdout.write(json.dumps({k: r[k] for k in r if k != "top_sources"},
                                ensure_ascii=False) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
