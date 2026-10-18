# -*- coding: utf-8 -*-
"""URL normalization and plain-language errors for Website Monitor and
Content Health. Offline: real sockets refuse."""

import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import content_health as CH      # noqa: E402
from atlas_services import website_monitor as WM      # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket.socket, "connect", boom)


class Resp:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text


class Getter:
    """head/get: a Resp for known URLs, or raise the given exception."""
    def __init__(self, pages=None, exc=None):
        self.pages, self.exc, self.calls = pages or {}, exc, []

    def _go(self, url):
        self.calls.append(url)
        if self.exc:
            raise self.exc
        return self.pages.get(url, Resp(404))

    def head(self, url, **k):
        return self._go(url)

    def get(self, url, **k):
        return self._go(url)


def test_url_normalization_prepends_https():
    assert WM.normalize_url("example.com") == ("https://example.com", None)
    assert WM.normalize_url("  Example.COM/About/ ") == (
        "https://example.com/About", None)
    assert WM.normalize_url("http://www.Site.ae/") == ("http://www.site.ae",
                                                       None)
    # check_url fetches the normalized address and echoes the input
    g = Getter({"https://salehhaidar.com": Resp(200)})
    r = WM.check_url("salehhaidar.com", session=g)
    assert r["ok"] and r["checked_url"] == "https://salehhaidar.com"
    assert r["url"] == "salehhaidar.com" and g.calls == [
        "https://salehhaidar.com"]


def test_url_normalization_rejects_bare_word():
    for bad in ("localhost", "not-a-url", "", "   ", "two words.com",
                "https://", "example."):
        url, reason = WM.normalize_url(bad)
        assert url is None and reason == "invalid_domain", bad
    assert WM.normalize_url("ftp://example.com") == (None,
                                                     "unsupported_scheme")
    r = WM.check_url("hello")
    assert r["error"] == "invalid_url" and r["reason"] == "invalid_domain"
    assert r["message"] == "Please enter a valid domain (example.com)"
    c = CH.scan_site("hello", getter=Getter())
    assert c["ok"] is False and c["reason"] == "invalid_url"
    assert c["message"] == "Please enter a valid domain (example.com)"


def test_connection_error_shows_plain_message():
    r = WM.check_url("down.example", session=Getter(exc=ConnectionError("x")))
    assert r["ok"] is False and r["error"] == "ConnectionError"
    assert r["message"] == "Could not reach the site"
    t = WM.check_url("slow.example", session=Getter(exc=TimeoutError("x")))
    assert t["message"] == "The site took too long to respond"

    class SSLError(ConnectionError):          # requests' SSLError shape
        pass
    s = WM.check_url("bad-cert.example", session=Getter(exc=SSLError("x")))
    assert s["reason"] == "ssl_error" and s["message"] == \
        "SSL certificate error"
    # content health: an unreachable site says so in plain words, and the
    # machine-readable reason is kept
    c = CH.scan_site("down.example", getter=Getter(exc=ConnectionError("x")))
    assert c["ok"] is False
    assert c["reason"] == "robots_unreachable:ConnectionError"
    assert c["message"] == "Could not reach the site"
    # a robots.txt that blocks a page is explained, not just flagged
    g = Getter({"https://site.example/robots.txt":
                Resp(200, "User-agent: *\nDisallow: /\n")})
    blocked = CH.scan_site("site.example", getter=g)
    assert blocked["ok"] and blocked["pages"][0]["message"] == \
        "The site's robots.txt blocks this check"
