# -*- coding: utf-8 -*-
"""ATLAS service: compare two business websites on on-page signals.

For each domain it fetches the homepage once and records status, title,
meta description, a viewport tag, analytics (gtag / googletagmanager),
schema.org presence, the html lang attribute and content length. Each
domain scores 0-100 by how many signals are present. No API key; requests
only. A dead or unreachable domain scores 0 rather than raising.

CLI:
    python -m atlas_services.competitive_analysis --a X --b Y --out path
"""

from __future__ import annotations

import argparse
import json
import re
import sys

try:
    import requests
except ImportError:
    requests = None

TIMEOUT_S = 12
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
# signal -> points (sum = 100)
WEIGHTS = {"reachable": 20, "title": 15, "meta_description": 15,
           "viewport": 10, "analytics": 10, "schema_org": 10,
           "html_lang": 10, "substantial_content": 10}


def _url(domain: str) -> str:
    d = (domain or "").strip()
    if not d.lower().startswith(("http://", "https://")):
        d = "https://" + d.lstrip("/")
    return d


def _search(pat: str, html: str) -> bool:
    return bool(re.search(pat, html, re.I))


def probe(domain: str, *, getter=None) -> dict:
    out = {"domain": domain, "reachable": False, "status_code": None,
           "title": None, "meta_description": None, "viewport": False,
           "analytics": False, "schema_org": False, "html_lang": None,
           "content_length": 0, "error": None}
    getter = getter or requests
    if getter is None:
        out["error"] = "requests_not_installed"
        return out
    try:
        resp = getter.get(_url(domain), timeout=TIMEOUT_S,
                         headers={"User-Agent": UA}, allow_redirects=True)
    except Exception as e:
        out["error"] = type(e).__name__
        return out
    out["status_code"] = resp.status_code
    html = resp.text or ""
    out["content_length"] = len(html)
    out["reachable"] = 200 <= resp.status_code < 400
    if not out["reachable"]:
        return out
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        out["title"] = " ".join(m.group(1).split())[:160]
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content='
                  r'["\'](.*?)["\']', html, re.I | re.S)
    if m:
        out["meta_description"] = " ".join(m.group(1).split())[:200]
    out["viewport"] = _search(r'name=["\']viewport["\']', html)
    out["analytics"] = _search(r"googletagmanager\.com|gtag\(|"
                               r"google-analytics\.com", html)
    out["schema_org"] = _search(r"schema\.org|application/ld\+json", html)
    m = re.search(r"<html[^>]+lang=['\"]([a-zA-Z\-]+)", html, re.I)
    if m:
        out["html_lang"] = m.group(1)
    return out


def _score(p: dict) -> tuple[int, dict]:
    present = {
        "reachable": p["reachable"],
        "title": bool(p["title"]),
        "meta_description": bool(p["meta_description"]),
        "viewport": p["viewport"], "analytics": p["analytics"],
        "schema_org": p["schema_org"], "html_lang": bool(p["html_lang"]),
        "substantial_content": p["content_length"] >= 2000,
    }
    score = sum(WEIGHTS[k] for k, ok in present.items() if ok)
    return min(100, score), present


def compare(domain_a: str, domain_b: str, *, getter=None) -> dict:
    if not (domain_a or "").strip() or not (domain_b or "").strip():
        return {"ok": False, "reason": "two_domains_required"}
    pa, pb = probe(domain_a, getter=getter), probe(domain_b, getter=getter)
    sa, br_a = _score(pa)
    sb, br_b = _score(pb)
    pa["signals"], pb["signals"] = br_a, br_b
    winner = "a" if sa > sb else "b" if sb > sa else "tie"
    return {"ok": True, "domain_a": domain_a, "domain_b": domain_b,
            "probe_a": pa, "probe_b": pb, "score_a": sa, "score_b": sb,
            "winner": winner, "reason": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.competitive_analysis")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    r = compare(a.a, a.b)
    if a.out and r.get("ok"):
        from pathlib import Path
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    sys.stdout.write(json.dumps({k: r[k] for k in
                                 ("ok", "domain_a", "domain_b", "score_a",
                                  "score_b", "winner", "reason")
                                 if k in r}, ensure_ascii=False) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
