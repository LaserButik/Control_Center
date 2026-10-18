# -*- coding: utf-8 -*-
"""ATLAS service: a light SEO read on a domain, via the Serper API.

Needs SERPER_API_KEY in the environment. Without it, every function returns
{"ok": False, "reason": "serper_not_configured"} and makes NO network call,
so the service is safe to import and call in any environment.

CLI:
    python -m atlas_services.seo_intelligence --domain example.ae
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    requests = None

SERPER_URL = "https://google.serper.dev/search"
TIMEOUT_S = 15


def _key() -> str:
    return (os.getenv("SERPER_API_KEY") or "").strip()


def _clean_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    for pre in ("https://", "http://"):
        if d.startswith(pre):
            d = d[len(pre):]
    return d.strip("/").split("/")[0]


def check_domain(domain: str, *, poster=None) -> dict:
    """Top organic keywords and a rough backlink/visibility read for a
    domain. `poster(url, headers, json)` is injected by tests; by default
    it posts with requests. No key -> no call."""
    d = _clean_domain(domain)
    if not d:
        return {"ok": False, "reason": "invalid_domain"}
    key = _key()
    if not key:
        return {"ok": False, "reason": "serper_not_configured", "domain": d}
    if poster is None and requests is None:
        return {"ok": False, "reason": "requests_not_installed", "domain": d}

    def _post(url, headers, body):
        resp = requests.post(url, headers=headers, json=body,
                             timeout=TIMEOUT_S)
        return resp.status_code, (resp.json() if resp.content else {})
    post = poster or _post
    try:
        status, data = post(SERPER_URL,
                            {"X-API-KEY": key,
                             "Content-Type": "application/json"},
                            {"q": "site:%s" % d, "num": 10})
    except Exception as e:
        return {"ok": False, "reason": "request_failed:%s"
                % type(e).__name__, "domain": d}
    if not 200 <= int(status) < 300:
        return {"ok": False, "reason": "serper_http_%s" % status,
                "domain": d}
    data = data or {}
    organic = data.get("organic") or []
    keywords = []
    for item in organic:
        kw = item.get("title") or item.get("snippet") or ""
        if kw:
            keywords.append(" ".join(kw.split())[:80])
    return {"ok": True, "domain": d,
            "indexed_results": len(organic),
            "backlinks_estimate": (data.get("searchInformation") or {})
            .get("totalResults"),
            "top_keywords": keywords[:10],
            "domain_age_days": None}      # not available from this endpoint


def compare_domains(domains: list, *, poster=None) -> list[dict]:
    return [check_domain(d, poster=poster) for d in (domains or [])]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.seo_intelligence")
    ap.add_argument("--domain", required=True)
    a = ap.parse_args(argv)
    r = check_domain(a.domain)
    sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
