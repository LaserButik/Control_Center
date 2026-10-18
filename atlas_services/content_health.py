# -*- coding: utf-8 -*-
"""ATLAS service: a small content-health crawl of one site.

Breadth-first from a base URL, up to max_pages same-host pages. Each page's
status is recorded, its links are collected, and 4xx/5xx/timeout links are
marked broken. robots.txt is honoured the same way outreach/verifier.py
does it: a disallowed path is skipped, a missing (4xx) robots.txt means no
rules, and an unreachable (5xx/timeout) robots.txt stops the crawl. requests
only — no Playwright.

CLI:
    python -m atlas_services.content_health --url https://example.ae --max 20
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

try:
    import requests
except ImportError:
    requests = None

from atlas_services.website_monitor import (MESSAGES, classify_error,
                                            normalize_url)

DEFAULT_MAX_PAGES = 20
DEFAULT_TIMEOUT_S = 10
UA = "AIMentorsAgency-ContentHealth/1.0 (+honours robots.txt)"


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def _links(html: str, base: str) -> list[str]:
    p = _LinkParser()
    try:
        p.feed(html or "")
    except Exception:
        return []
    out, seen = [], set()
    for href in p.hrefs:
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        u = urljoin(base, href).split("#")[0]
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _host(url: str) -> str:
    """The site's host, lowercased, with a leading "www." dropped so that
    example.com and www.example.com count as the same site."""
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _robots(base: str, getter, timeout_s: float):
    """(RobotFileParser|None, stop_reason|None, message|None).
    None parser = allow all."""
    s = urlsplit(base)
    robots_url = "%s://%s/robots.txt" % (s.scheme or "https", s.netloc)
    try:
        resp = getter.get(robots_url, timeout=timeout_s,
                          headers={"User-Agent": UA})
    except Exception as e:
        return (None, "robots_unreachable:%s" % type(e).__name__,
                MESSAGES[classify_error(e)])
    if resp.status_code >= 500:
        return (None, "robots_unreachable:HTTP %s" % resp.status_code,
                "The site's robots.txt answered with a server error (HTTP "
                "%s), so the scan was stopped" % resp.status_code)
    rp = RobotFileParser()
    if 200 <= resp.status_code < 300:
        rp.parse((resp.text or "").splitlines())
    else:
        rp.parse([])                          # 4xx: no rules
    return rp, None, None


def scan_site(base_url: str, max_pages: int = DEFAULT_MAX_PAGES,
              timeout_s: float = DEFAULT_TIMEOUT_S, *, getter=None) -> dict:
    """Crawl one site. `reason` keeps the machine code (invalid_url,
    robots_unreachable:<cause>); `message` says it in plain words. Each
    page: url, status_code, response_ms, links, and reason/message when
    it failed or was skipped."""
    out = {"ok": False, "base_url": base_url, "pages_scanned": 0,
           "pages": [], "broken_links": [], "robots_respected": True,
           "reason": None, "message": None}
    target, bad = normalize_url(base_url)
    if bad:
        out["reason"] = "invalid_url"
        out["message"] = MESSAGES[bad]
        return out
    base_url = out["base_url"] = target
    getter = getter or requests
    if getter is None:
        out["reason"] = "requests_not_installed"
        out["message"] = MESSAGES["requests_not_installed"]
        return out
    cap = max(1, int(max_pages))
    host = _host(base_url)

    rp, stop, why = _robots(base_url, getter, timeout_s)
    if stop:
        out["reason"] = stop               # robots unreachable: do not crawl
        out["message"] = why
        return out

    def allowed(u: str) -> bool:
        return rp is None or rp.can_fetch(UA, u)

    seen, broken = set(), []
    queue = deque([base_url])
    while queue and len(out["pages"]) < cap:
        url = queue.popleft()
        if url.rstrip("/") in seen:          # /page and /page/ are one page
            continue
        seen.add(url.rstrip("/"))
        if not allowed(url):
            out["pages"].append({"url": url, "status_code": None,
                                 "skipped": "robots_disallowed",
                                 "reason": "robots_disallowed",
                                 "message": MESSAGES["robots_disallowed"]})
            continue
        t0 = time.perf_counter()
        try:
            resp = getter.get(url, timeout=timeout_s,
                             headers={"User-Agent": UA})
            status = resp.status_code
            html = resp.text if status < 400 else ""
        except Exception as e:
            code = classify_error(e)
            fail = {"url": url, "status_code": None,
                    "error": type(e).__name__, "reason": code,
                    "message": MESSAGES[code],
                    "response_ms": int((time.perf_counter() - t0) * 1000)}
            out["pages"].append(dict(fail))
            broken.append(fail)
            continue
        page = {"url": url, "status_code": status, "links": 0,
                "response_ms": int((time.perf_counter() - t0) * 1000)}
        if status >= 400:
            page.update(reason="http_error",
                        message="Broken page (HTTP %s)" % status)
            broken.append({"url": url, "status_code": status,
                           "reason": "http_error",
                           "message": page["message"]})
        else:
            links = _links(html, url)
            page["links"] = len(links)
            for u in links:
                if _host(u) == host and u.rstrip("/") not in seen and \
                        len(seen) + len(queue) < cap * 3:
                    queue.append(u)
        out["pages"].append(page)
    out["pages_scanned"] = len(out["pages"])
    out["broken_links"] = broken
    out["broken_count"] = len(broken)
    out["ok"] = True
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.content_health")
    ap.add_argument("--url", required=True)
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_PAGES)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    report = scan_site(a.url, max_pages=a.max, timeout_s=a.timeout)
    if a.out and report.get("ok"):
        from pathlib import Path
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False,
                                          indent=1), encoding="utf-8")
    sys.stdout.write(json.dumps({k: report[k] for k in
                                 ("ok", "base_url", "pages_scanned",
                                  "broken_count", "reason")
                                 if k in report}, ensure_ascii=False) + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
