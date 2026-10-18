# -*- coding: utf-8 -*-
"""ATLAS service: is a business's website up, and how fast?

A single HEAD request per URL (falling back to GET when HEAD is refused).
Synchronous and simple. robots.txt is NOT consulted: a HEAD to the homepage
of a business we are evaluating is the same request a human visitor's
browser makes, not crawling. Anything deeper (content_health) does honour
robots.txt.

CLI:
    python -m atlas_services.website_monitor --input <prospects.json> --out <report.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    import requests
except ImportError:                          # the CLI still reports cleanly
    requests = None

DEFAULT_TIMEOUT_S = 10
UA = "AIMentorsAgency-WebsiteMonitor/1.0 (+site availability check)"

# Plain-language reasons. Pages translate by code; `message` is the English.
MESSAGES = {
    "invalid_domain": "Please enter a valid domain (example.com)",
    "unsupported_scheme": "Only http:// and https:// addresses can be "
                          "checked",
    "connection_failed": "Could not reach the site",
    "timeout": "The site took too long to respond",
    "ssl_error": "SSL certificate error",
    "too_many_redirects": "The site keeps redirecting and never loads",
    "robots_disallowed": "The site's robots.txt blocks this check",
    "request_failed": "The request failed",
    "requests_not_installed": "The requests library is not installed",
}

_HOST = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
                   r"[a-z][a-z0-9-]{0,61}[a-z0-9]$")


def normalize_url(raw) -> tuple[str | None, str | None]:
    """("https://host/path", None), or (None, reason code) for input that is
    not a web address. "example.com" gets https://; the host is lowercased
    and a trailing slash dropped."""
    s = str(raw or "").strip()
    if not s or any(c.isspace() for c in s):
        return None, "invalid_domain"
    if "://" not in s:
        s = "https://" + s.lstrip("/")
    try:
        parts = urlsplit(s)
        port = parts.port
    except ValueError:
        return None, "invalid_domain"
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return None, "unsupported_scheme"
    host = (parts.hostname or "").lower().rstrip(".")
    if not _HOST.match(host):
        return None, "invalid_domain"
    netloc = host + (":%d" % port if port else "")
    return urlunsplit((scheme, netloc, parts.path.rstrip("/"), parts.query,
                       "")), None


def classify_error(exc: BaseException) -> str:
    """A reason code for a failed request, from the exception's class
    names (requests' and the standard library's alike)."""
    names = {c.__name__ for c in type(exc).__mro__}
    if names & {"SSLError", "SSLCertVerificationError"}:
        return "ssl_error"
    if names & {"Timeout", "ConnectTimeout", "ReadTimeout", "TimeoutError",
                "timeout"}:
        return "timeout"
    if "TooManyRedirects" in names:
        return "too_many_redirects"
    if names & {"ConnectionError", "ConnectionRefusedError",
                "ConnectionResetError", "NameResolutionError", "gaierror",
                "NewConnectionError", "MaxRetryError"}:
        return "connection_failed"
    return "request_failed"


def _fail(out: dict, reason: str) -> dict:
    out["reason"] = reason
    out["message"] = MESSAGES.get(reason, MESSAGES["request_failed"])
    return out


def check_url(url: str, timeout_s: float = DEFAULT_TIMEOUT_S,
              session=None) -> dict:
    """{ok, url, checked_url, status_code, response_ms, error, reason,
    message}. `url` is echoed as given; `checked_url` is what was fetched.
    `error` keeps the raw code (invalid_url / exception class name);
    `reason` + `message` say it in plain words. Never raises."""
    out = {"ok": False, "url": url, "checked_url": None, "status_code": None,
           "response_ms": None, "error": None, "reason": None,
           "message": None}
    target, bad = normalize_url(url)
    if bad:
        out["error"] = "invalid_url"
        return _fail(out, bad)
    out["checked_url"] = target
    if requests is None:
        out["error"] = "requests_not_installed"
        return _fail(out, "requests_not_installed")
    getter = session or requests
    t0 = time.perf_counter()
    try:
        resp = getter.head(target, timeout=timeout_s, allow_redirects=True,
                           headers={"User-Agent": UA})
        if resp.status_code in (403, 405, 501):   # some hosts refuse HEAD
            resp = getter.get(target, timeout=timeout_s, allow_redirects=True,
                             headers={"User-Agent": UA}, stream=True)
    except Exception as e:                   # requests.RequestException etc.
        out["response_ms"] = int((time.perf_counter() - t0) * 1000)
        out["error"] = type(e).__name__
        return _fail(out, classify_error(e))
    out["response_ms"] = int((time.perf_counter() - t0) * 1000)
    out["status_code"] = resp.status_code
    out["ok"] = 200 <= resp.status_code < 400
    if not out["ok"]:
        out["reason"] = "http_error"
        out["message"] = "The site answered HTTP %s" % resp.status_code
    return out


def check_many(urls: list, max_concurrent: int = 5,
               timeout_s: float = DEFAULT_TIMEOUT_S) -> list[dict]:
    """Check several URLs. A small thread pool; order of input preserved."""
    clean = [u for u in (urls or []) if isinstance(u, str) and u.strip()]
    if not clean:
        return []
    if requests is None:
        return [check_url(u, timeout_s) for u in clean]
    from concurrent.futures import ThreadPoolExecutor
    session = requests.Session()
    workers = max(1, min(int(max_concurrent), 16))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(
            lambda u: check_url(u, timeout_s, session=session), clean))


def run_for_prospect_file(path: str, timeout_s: float = DEFAULT_TIMEOUT_S
                          ) -> dict:
    """Read a prospects/scrape/scored JSON file, check every website in it,
    and return a report. No file is written."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"ok": False, "reason": "input_unreadable:%s"
                % type(e).__name__, "input": str(path)}
    rows = data.get("prospects", data) if isinstance(data, dict) else data
    pairs = [(p.get("company_name"), p.get("website")) for p in rows
             if isinstance(p, dict) and p.get("website")]
    results = check_many([w for _, w in pairs], timeout_s=timeout_s)
    by_url = {r["url"]: r for r in results}
    checked = [{"company_name": name, **by_url.get(url, {"url": url})}
               for name, url in pairs]
    alive = sum(1 for r in checked if r.get("ok"))
    return {"ok": True, "input": str(path), "checked": len(checked),
            "alive": alive, "down": len(checked) - alive,
            "results": checked}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.website_monitor")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    a = ap.parse_args(argv)
    report = run_for_prospect_file(a.input, timeout_s=a.timeout)
    if a.out and report.get("ok"):
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False,
                                          indent=1), encoding="utf-8")
    sys.stdout.write(json.dumps({k: report[k] for k in report
                                 if k != "results"}, ensure_ascii=False)
                     + "\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
