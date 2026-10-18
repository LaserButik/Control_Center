# -*- coding: utf-8 -*-
"""ATLAS service: a rough backlink read for a domain via the Serper API.

Two searches surface pages that reference the domain; referring domains are
extracted from the result URLs and deduplicated. This is an estimate from
public search results, not a crawl of a link index. Needs SERPER_API_KEY;
without it, no network call is made.

CLI:
    python -m atlas_services.backlink_intelligence --domain X --out path
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


def _key() -> str:
    return (os.getenv("SERPER_API_KEY") or "").strip()


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _clean_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    for pre in ("https://", "http://"):
        if d.startswith(pre):
            d = d[len(pre):]
    return d.strip("/").split("/")[0]


def _default_poster(key: str):
    def _post(body):
        resp = requests.post(SERPER_URL, headers={"X-API-KEY": key,
                             "Content-Type": "application/json"},
                             json=body, timeout=TIMEOUT_S)
        return resp.status_code, (resp.json() if resp.content else {})
    return _post


def check_backlinks(domain: str, country: str = "us", *,
                    poster=None) -> dict:
    d = _clean_domain(domain)
    if not d:
        return {"ok": False, "reason": "invalid_domain"}
    key = _key()
    if not key:
        return {"ok": False, "reason": "serper_not_configured", "domain": d}
    if poster is None and requests is None:
        return {"ok": False, "reason": "requests_not_installed", "domain": d}
    post = poster or _default_poster(key)
    queries = ["link:%s" % d, '"%s" -site:%s' % (d, d)]
    referrers, total = {}, 0
    for q in queries:
        try:
            status, data = post({"q": q, "gl": country, "num": 20})
        except Exception as e:
            return {"ok": False, "reason": "request_failed:%s"
                    % type(e).__name__, "domain": d}
        if not 200 <= int(status) < 300:
            return {"ok": False, "reason": "serper_http_%s" % status,
                    "domain": d}
        info = (data or {}).get("searchInformation") or {}
        total = max(total, int(str(info.get("totalResults") or "0")
                               .replace(",", "") or 0))
        for item in (data or {}).get("organic", []):
            url = item.get("link") or item.get("url") or ""
            host = _host(url)
            if not host or host == d or host.endswith("." + d):
                continue                     # skip the domain's own pages
            referrers.setdefault(host, {"url": url,
                                        "title": (item.get("title")
                                                  or "")[:120]})
    sample = sorted(referrers)
    return {"ok": True, "domain": d,
            "estimated_backlinks": total,
            "referring_domains_count": len(referrers),
            "referring_domains_sample": sample[:25],
            "top_referrers": list(referrers.values())[:10], "reason": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.backlink_intelligence")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--country", default="us")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    r = check_backlinks(a.domain, a.country)
    if a.out and r.get("ok"):
        from pathlib import Path
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    sys.stdout.write(json.dumps({k: r[k] for k in r
                                 if k != "top_referrers"},
                                ensure_ascii=False) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
