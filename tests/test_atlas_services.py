# -*- coding: utf-8 -*-
"""ATLAS services, offline. website_monitor and content_health take an
injected getter; seo_intelligence an injected poster. Real sockets refuse,
and SERPER_API_KEY is cleared."""

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import content_health as CH      # noqa: E402
from atlas_services import seo_intelligence as SEO    # noqa: E402
from atlas_services import website_monitor as WM      # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)


class FakeResp:
    def __init__(self, status=200, text="", json_data=None):
        self.status_code = status
        self.text = text
        self.content = (text or "x").encode()
        self._json = json_data or {}

    def json(self):
        return self._json


class FakeGetter:
    """A requests-like object: maps URL -> FakeResp, or raises for a URL."""
    def __init__(self, pages=None, raise_for=()):
        self.pages = pages or {}
        self.raise_for = set(raise_for)
        self.calls = []

    def _resp(self, url):
        self.calls.append(url)
        if url in self.raise_for:
            raise TimeoutError("timed out")
        return self.pages.get(url, FakeResp(404, ""))

    def head(self, url, **k):
        return self._resp(url)

    def get(self, url, **k):
        return self._resp(url)


def test_website_monitor_reports_failure_on_bad_url():
    assert WM.check_url("not-a-url")["error"] == "invalid_url"
    g = FakeGetter(raise_for={"https://down.ae"})
    r = WM.check_url("https://down.ae", session=g)
    assert r["ok"] is False and r["error"] == "TimeoutError"
    assert r["response_ms"] is not None
    g2 = FakeGetter({"https://up.ae": FakeResp(200)})
    r2 = WM.check_url("https://up.ae", session=g2)
    assert r2["ok"] is True and r2["status_code"] == 200


def test_website_monitor_no_network_when_disabled(monkeypatch):
    # with requests missing, no network is attempted and it says so
    monkeypatch.setattr(WM, "requests", None)
    r = WM.check_url("https://example.ae")
    assert r["ok"] is False and r["error"] == "requests_not_installed"
    assert WM.check_many([]) == []           # nothing to do, no call


def test_seo_returns_not_configured_without_key():
    called = []

    def poster(*a, **k):
        called.append(a)
        return 200, {}
    r = SEO.check_domain("example.ae", poster=poster)
    assert r == {"ok": False, "reason": "serper_not_configured",
                 "domain": "example.ae"}
    assert called == []                      # no key -> no call at all
    # with a key, the injected poster is used and parsed
    import os
    os.environ["SERPER_API_KEY"] = "test-key"
    try:
        def poster2(url, headers, body):
            assert headers["X-API-KEY"] == "test-key"
            return 200, {"organic": [{"title": "Example AE - Home"},
                                     {"snippet": "Shop online"}],
                         "searchInformation": {"totalResults": "1230"}}
        r = SEO.check_domain("https://example.ae/path", poster=poster2)
        assert r["ok"] and r["domain"] == "example.ae"
        assert r["top_keywords"][0] == "Example AE - Home"
        assert r["backlinks_estimate"] == "1230"
    finally:
        del os.environ["SERPER_API_KEY"]


def test_content_health_respects_max_pages():
    def page(links):
        body = "".join('<a href="%s">x</a>' % u for u in links)
        return FakeResp(200, "<html>%s</html>" % body)
    pages = {"https://site.ae/robots.txt": FakeResp(404, "")}
    # a hub that links to 10 children; max_pages should cap the scan
    children = ["https://site.ae/p%d" % i for i in range(10)]
    pages["https://site.ae"] = page(children)
    for c in children:
        pages[c] = page([])
    g = FakeGetter(pages)
    r = CH.scan_site("https://site.ae", max_pages=3, getter=g)
    assert r["ok"] and r["pages_scanned"] == 3   # never more than max_pages
    assert all(p["url"].startswith("https://site.ae") for p in r["pages"])


def test_content_health_marks_404_as_broken():
    pages = {
        "https://site.ae/robots.txt": FakeResp(200,
                                               "User-agent: *\nAllow: /\n"),
        "https://site.ae": FakeResp(200,
                                    '<a href="/ok">o</a><a href="/missing">'
                                    'm</a><a href="/boom">b</a>'),
        "https://site.ae/ok": FakeResp(200, "<html>fine</html>"),
        "https://site.ae/missing": FakeResp(404, ""),
    }
    g = FakeGetter(pages, raise_for={"https://site.ae/boom"})
    r = CH.scan_site("https://site.ae", max_pages=10, getter=g)
    broken = {b["url"]: b for b in r["broken_links"]}
    assert "https://site.ae/missing" in broken
    assert broken["https://site.ae/missing"]["status_code"] == 404
    assert broken["https://site.ae/boom"]["error"] == "TimeoutError"
    assert r["broken_count"] == 2
    # a robots.txt that is unreachable (5xx) stops the crawl
    g2 = FakeGetter({"https://x.ae/robots.txt": FakeResp(503, "")})
    r2 = CH.scan_site("https://x.ae", getter=g2)
    assert r2["ok"] is False and r2["reason"].startswith("robots_unreachable")


# ───────────── Phase J+K: four new ATLAS services ─────────────

from atlas_services import reputation_monitor as REP       # noqa: E402
from atlas_services import backlink_intelligence as BL      # noqa: E402
from atlas_services import competitive_analysis as COMP     # noqa: E402
from atlas_services import content_distribution as CD       # noqa: E402


def test_reputation_returns_not_configured_without_key():
    calls = []
    r = REP.check_brand("ACME AE", poster=lambda b: calls.append(b))
    assert r == {"ok": False, "reason": "serper_not_configured",
                 "brand": "ACME AE"}
    assert calls == []                       # no key -> no query at all


def test_reputation_classifies_positive_negative(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "k")
    pages = {
        '"ACME"': {"organic": [
            {"title": "ACME is excellent and highly recommended",
             "link": "https://a.example/1", "snippet": "great service"}]},
        '"ACME" review': {"organic": [
            {"title": "ACME scam warning", "link": "https://b.example/2",
             "snippet": "complaint and refund"}]},
        '"ACME" praise': {"organic": [
            {"title": "ACME opens new office", "link": "https://c.example/3",
             "snippet": "news"},
            {"title": "dup", "link": "https://a.example/1"}]},   # dup URL
        # the dedicated complaint query: a NEGATED complaint is not negative
        '"ACME" complaint': {"organic": [
            {"title": "ACME: no complaints in 5 years",
             "link": "https://d.example/4",
             "snippet": "customers say highly recommended"}]}}
    sent = []

    def poster(body):
        sent.append(body["q"])
        return 200, pages[body["q"]]
    r = REP.check_brand("ACME", poster=poster)
    assert sent == ['"ACME"', '"ACME" review', '"ACME" praise',
                    '"ACME" complaint']                  # 4 plain queries
    assert not any("(" in q or " OR " in q for q in sent)
    assert r["ok"] and r["total_mentions"] == 4       # the dup was dropped
    assert r["positive_hits"] == 2 and r["negative_hits"] == 1
    assert r["neutral_hits"] == 1
    assert _classify_ok()


def _classify_ok():
    assert REP._classify("excellent and recommended") == "positive"
    assert REP._classify("scam complaint") == "negative"
    assert REP._classify("ممتاز وموثوق") == "positive"
    assert REP._classify("نصب واحتيال") == "negative"
    assert REP._classify("opened a new branch") == "neutral"
    assert REP._classify("great but also a complaint") == "neutral"
    # negations from the complaint query are not counted as negative
    assert REP._classify("No complaints so far") == "neutral"
    assert REP._classify("not a scam, very professional") == "positive"
    assert REP._classify("لا توجد شكاوى وخدمة ممتازة") == "positive"
    assert REP._classify("customer complaint about delays") == "negative"
    return True


def test_backlinks_returns_not_configured_without_key():
    calls = []
    r = BL.check_backlinks("example.ae", poster=lambda b: calls.append(b))
    assert r == {"ok": False, "reason": "serper_not_configured",
                 "domain": "example.ae"}
    assert calls == []


def test_backlinks_extracts_referring_domains(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "k")

    def poster(body):
        return 200, {"searchInformation": {"totalResults": "3,400"},
                     "organic": [
                         {"link": "https://news.ae/story", "title": "Story"},
                         {"link": "https://www.blog.ae/post", "title": "P"},
                         {"link": "https://example.ae/self", "title": "self"},
                         {"link": "https://news.ae/another", "title": "A2"}]}
    r = BL.check_backlinks("https://example.ae/", poster=poster)
    assert r["ok"] and r["domain"] == "example.ae"
    assert r["estimated_backlinks"] == 3400
    assert r["referring_domains_sample"] == ["blog.ae", "news.ae"]  # no self
    assert r["referring_domains_count"] == 2


def test_competitive_compare_returns_score():
    class Resp:
        def __init__(self, status, text):
            self.status_code, self.text = status, text

    strong = ('<html lang="en"><head><title>Strong Co</title>'
              '<meta name="description" content="We do things">'
              '<meta name="viewport" content="width=device-width">'
              '<script src="https://www.googletagmanager.com/gtag/js">'
              '</script><script type="application/ld+json">{}</script>'
              '</head><body>' + ("x" * 2500) + "</body></html>")
    weak = "<html><head><title>Weak</title></head><body>hi</body></html>"

    class Getter:
        def get(self, url, **k):
            return Resp(200, strong if "strong" in url else weak)
    r = COMP.compare("strong.ae", "weak.ae", getter=Getter())
    assert r["ok"] and r["score_a"] == 100 and r["winner"] == "a"
    assert r["score_b"] < r["score_a"]
    assert r["probe_a"]["title"] == "Strong Co"
    assert r["probe_a"]["signals"]["schema_org"] is True


def test_competitive_handles_dead_domain():
    class Getter:
        def get(self, url, **k):
            raise ConnectionError("dead")
    r = COMP.compare("a.ae", "b.ae", getter=Getter())
    assert r["ok"] and r["score_a"] == 0 and r["score_b"] == 0
    assert r["winner"] == "tie"
    assert r["probe_a"]["reachable"] is False
    assert r["probe_a"]["error"] == "ConnectionError"


def test_content_distribution_writes_files_for_each_platform(tmp_path):
    src = tmp_path / "content.json"
    src.write_text(json.dumps({"items": [
        {"title": "AI employees for " + "x" * 300,
         "body": "Long body about marketing and automation and growth",
         "url": "https://example.com/p"},
        {"title": "Second", "body": "short", "url": "https://example.com/q"}
    ]}), encoding="utf-8")
    out = tmp_path / "posts"
    r = CD.prepare_posts(str(src), ["twitter", "linkedin", "generic"],
                         str(out))
    assert r["ok"] and r["items"] == 2
    assert len(r["files_written"]) == 6               # 2 items x 3 platforms
    names = sorted(p.name for p in out.iterdir())
    assert any(n.endswith("_twitter.txt") for n in names)
    tw = next(out.glob("01_*_twitter.txt")).read_text(encoding="utf-8")
    assert len(tw.split("\n")[0]) <= 280              # truncated to limit
    li = next(out.glob("01_*_linkedin.txt")).read_text(encoding="utf-8")
    assert "First comment:" in li and "#" in li
    bad = CD.prepare_posts(str(src), ["myspace"], str(out))
    assert bad == {"ok": False, "reason": "no_valid_platform",
                   "out_dir": str(out), "files_written": []}


def test_content_distribution_never_calls_network(tmp_path, monkeypatch):
    # there is no requests import to stub; prove by behaviour: a run with
    # the sockets guard (autouse) active completes and writes only files.
    src = tmp_path / "c.json"
    src.write_text(json.dumps([{"title": "T", "body": "B",
                                "url": "https://x/y"}]), encoding="utf-8")
    import sys as _sys
    assert "requests" not in getattr(CD, "__dict__", {})
    r = CD.prepare_posts(str(src), ["telegram", "facebook"],
                         str(tmp_path / "o"))
    assert r["ok"] and r["items"] == 1
    assert all(f.endswith(".txt") for f in r["files_written"])


def test_reputation_queries_avoid_parentheses():
    """All query strings built in check_brand must be free of
    parentheses and 'OR' operator (Serper answers HTTP 400 to Google's
    grouping syntax)."""
    import inspect
    from atlas_services import reputation_monitor as rm
    src = inspect.getsource(rm.check_brand)
    block = src.split('queries = [')[1].split(']')[0]
    assert "(" not in block
    assert "OR" not in block
