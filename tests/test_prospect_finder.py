# -*- coding: utf-8 -*-
"""ATLAS prospect finder. Serper is a fake http_post with fixture JSON,
pages come from a fake fetcher, Playwright is a fake page object (no
browser is launched), and sockets refuse."""

import contextlib
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import prospect_finder as PF      # noqa: E402

ALLOW = (200, "User-agent: *\nAllow: /\n")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setenv("SERPER_API_KEY", "test-key")


class Serper:
    """Fake Serper: query text -> organic results."""
    def __init__(self, by_query=None, default=None):
        self.by_query, self.default = by_query or {}, default or []
        self.queries = []

    def __call__(self, url, headers, body, timeout):
        assert headers["X-API-KEY"] == "test-key"
        self.queries.append(body["q"])
        return 200, {"organic": self.by_query.get(body["q"], self.default)}


class Fetcher:
    def __init__(self, pages=None):
        self.pages, self.calls = pages or {}, []

    def __call__(self, url):
        self.calls.append(url)
        return self.pages.get(url, (404, None, url))


def _serper(post, fetcher=None, **kw):
    return PF.find_via_serper("clinics", "AE", 20, http_post=post,
                              fetcher=fetcher or Fetcher(),
                              sleep=lambda s: None, **kw)


# ── Serper mode ──

def test_find_via_serper_uses_five_queries():
    post = Serper()
    sleeps = []
    r = PF.find_via_serper("clinics", "AE", 20, http_post=post,
                           fetcher=Fetcher(), sleep=sleeps.append)
    assert r["ok"] and r["serper_calls"] == 5
    assert post.queries == PF.build_queries("clinics", "AE")
    phrase = PF.SECTORS["clinics"]["en"][0]
    assert post.queries == [
        '"dental clinic" Dubai "info@"',
        '"dental clinic" "Abu Dhabi" "info@"',
        '"dental clinic" Sharjah "info@"',
        'site:*.ae "dental clinic" "info@"',
        'site:*.ae "dental clinic" "contact@"']
    # one phrase for all five, never the opposite country's TLD
    assert all(q.split('"')[1] == phrase for q in post.queries)
    assert not any(".sa" in q for q in post.queries)
    for city in ("Dubai", "Abu Dhabi", "Sharjah"):
        assert any(city in q for q in post.queries), city
    assert any(q.startswith("site:*.ae ") for q in post.queries)
    assert len(set(post.queries)) == 5               # no repeated credit
    assert sleeps == [1.5] * 4                       # between queries only
    # Saudi runs mirror it with Saudi cities and .sa only
    sa = PF.build_queries("clinics", "SA")
    assert sa[:3] == ['"dental clinic" Riyadh "info@"',
                      '"dental clinic" Jeddah "info@"',
                      '"dental clinic" Dammam "info@"']
    assert not any(".ae" in q for q in sa)
    # the first phrase is used; an empty first phrase falls back
    assert PF.sector_phrase("restaurants") == "restaurant"
    import copy
    saved = copy.deepcopy(PF.SECTORS)
    try:
        PF.SECTORS["salons"]["en"] = ["", "hair salon"]
        assert PF.build_queries("salons", "AE")[0] == \
            '"hair salon" Dubai "info@"'
    finally:
        PF.SECTORS.clear()
        PF.SECTORS.update(saved)
    # a result's country still comes from its own .ae / .sa domain
    sa_item = {"title": "Riyadh Smile Clinic", "snippet": "info@smile.sa",
               "link": "https://smile.sa/"}
    r = PF.find_via_serper("clinics", "AE", 20, fetcher=Fetcher(),
                           sleep=lambda s: None, http_post=Serper(
                               by_query={post.queries[0]: [sa_item]}))
    assert r["companies"][0]["country"] == "SA"


def test_uae_run_never_targets_sa():
    """A UAE run must never send a .sa query."""
    from atlas_services import prospect_finder as pf
    queries = pf.plan("clinics", "AE")["queries"]
    assert all(".sa" not in q for q in queries)
    assert any(".ae" in q for q in queries)
    # all five sectors, and the multi-sector form the page uses
    full = pf.plan(list(pf.SECTORS), "AE")
    assert len(full["queries"]) == 25
    assert all(".sa" not in q for q in full["queries"])


def test_find_via_serper_extracts_email_from_snippet():
    item = {"title": "Smile Dental Clinic | Dubai",
            "link": "https://www.smileclinic.ae/contact",
            "snippet": "Book now: info@SmileClinic.ae, +971 4 555 0101"}
    f = Fetcher()
    r = _serper(Serper(default=[item]), f)
    c = r["companies"][0]
    assert c["email"] == "info@smileclinic.ae"
    assert c["phone_e164"] == "+97145550101"
    assert c["company_name"] == "Smile Dental Clinic"
    assert c["website"] == "https://smileclinic.ae"
    assert c["confidence"] == "high"                 # email on own domain
    assert c["source"] == "serper" and c["city"] == "Dubai"
    assert f.calls == [] and r["pages_fetched"] == 0  # no page needed


def test_find_via_serper_fetches_page_when_no_email_in_snippet():
    url = "https://oasis-dental.ae/about"
    item = {"title": "Oasis Dental", "link": url, "snippet": "Call us today"}
    page = ('<html><head><title>Oasis Dental Centre - Home</title>'
            '<meta property="og:site_name" content="Oasis Dental Centre">'
            '<link rel="canonical" href="https://www.oasis-dental.ae/"></head>'
            '<body><a href="mailto:Hello@Oasis-Dental.ae">mail</a>'
            '<a href="tel:+97143334444">call</a></body></html>')
    f = Fetcher({"https://oasis-dental.ae/robots.txt": ALLOW,
                 url: (200, page, url)})
    r = _serper(Serper(by_query={PF.build_queries("clinics", "AE")[0]:
                                 [item]}), f)
    assert f.calls == ["https://oasis-dental.ae/robots.txt", url]
    assert r["pages_fetched"] == 1
    c = r["companies"][0]
    assert (c["company_name"], c["email"], c["phone_e164"]) == (
        "Oasis Dental Centre", "hello@oasis-dental.ae", "+97143334444")
    assert c["email_found_on"] == "page"


def test_find_via_serper_skips_social_and_directory_domains():
    items = [{"title": "x", "link": "https://www.facebook.com/clinic",
              "snippet": "info@a.ae"},
             {"title": "x", "link": "https://ae.linkedin.com/company/x",
              "snippet": "info@b.ae"},
             {"title": "x", "link": "https://www.tripadvisor.com/x",
              "snippet": "info@c.ae"},
             {"title": "x", "link": "https://www.instagram.com/x",
              "snippet": "info@d.ae"},
             {"title": "x", "link": "https://www.dha.gov.ae/clinics",
              "snippet": "info@e.ae"},
             {"title": "x", "link": "https://www.uaeu.ac.ae/x",
              "snippet": "info@f.ae"},
             {"title": "Real Clinic", "link": "https://realclinic.ae/",
              "snippet": "info@realclinic.ae"}]
    f = Fetcher()
    r = _serper(Serper(default=items), f)
    assert [c["website"] for c in r["companies"]] == ["https://realclinic.ae"]
    assert f.calls == []
    assert PF._skip_domain("moh.gov.sa") and PF._skip_domain("uni.edu.sa")


def test_find_via_serper_respects_robots_disallow():
    url = "https://private-clinic.ae/team"
    item = {"title": "Private Clinic", "link": url, "snippet": "no email"}
    f = Fetcher({"https://private-clinic.ae/robots.txt":
                 (200, "User-agent: *\nDisallow: /\n"),
                 url: (200, '<a href="mailto:x@private-clinic.ae">m</a>',
                       url)})
    r = _serper(Serper(default=[item]), f)
    assert url not in f.calls                       # the page is never read
    assert r["companies"] == [] and r["pages_fetched"] == 0
    assert any(w.startswith("robots_disallowed") for w in r["warnings"])
    # robots.txt that answers 5xx: the host is treated as disallowed
    f2 = Fetcher({"https://private-clinic.ae/robots.txt": (503, None)})
    r2 = _serper(Serper(default=[item]), f2)
    assert url not in f2.calls
    assert any(w.startswith("robots_unreachable") for w in r2["warnings"])


def test_find_via_serper_caps_serper_calls_at_thirty():
    budget = PF.Budget(max_serper_calls=999)        # cannot exceed 30
    assert budget.max_serper_calls == 30
    post = Serper()
    runs = [PF.find_via_serper(s, c, 20, http_post=post, fetcher=Fetcher(),
                               sleep=lambda s: None, budget=budget)
            for c in ("AE", "SA") for s in PF.SECTORS]   # would be 50
    assert len(post.queries) == 30 and budget.serper_calls == 30
    assert sum(r["serper_calls"] for r in runs) == 30
    assert any("serper_cap_reached" in w for r in runs
               for w in r["warnings"])
    # and with no key at all, nothing is sent
    import os
    os.environ.pop("SERPER_API_KEY")
    post2 = Serper()
    r = PF.find_via_serper("clinics", http_post=post2, sleep=lambda s: None)
    assert post2.queries == [] and "serper_not_configured" in r["warnings"]


# ── Playwright mode (fake page, no browser) ──

YELLO = ('<html><body><div class="company with_img" data-cmpid="1">'
         '<div class="company_header"><h3><a href="/company/1/smile-dental">'
         'Smile Dental Clinic LLC</a></h3><div class="address">Al Wasl, '
         '<b>Dubai</b>, UAE</div></div><div class="company_btns">'
         '+971 4 555 0101</div></div>'
         '<div class="company" data-cmpid="2"><div class="company_header">'
         '<h3><a href="/company/2/pearl">Pearl Medical Centre</a></h3>'
         '<div class="address"><b>Dubai</b>, UAE</div></div>'
         '<span>04 222 3333</span></div></body></html>')


class FakePage:
    def __init__(self, pages):
        self.pages, self.visited = pages, []
        self._html, self._url = "", ""

    def goto(self, url, timeout_ms=30000):
        self.visited.append(url)
        status, html, final = self.pages.get(url, (200, YELLO, url))
        self._html, self._url = html, final
        return status

    def content(self):
        return self._html

    @property
    def url(self):
        return self._url


def _factory(page):
    @contextlib.contextmanager
    def f():
        yield page
    return f


def _pw(page, robots=ALLOW, **kw):
    return PF.find_via_playwright(
        "clinics", "AE", 60, page_factory=_factory(page),
        robots_fetcher=lambda u: robots, sleep=lambda s: None, **kw)


def test_find_via_playwright_respects_robots_disallow():
    page = FakePage({})
    r = _pw(page, robots=(200, "User-agent: *\nDisallow: /category/\n"))
    assert page.visited == []                        # nothing loaded
    assert r["companies"] == []
    assert any("Yello UAE skipped: robots_disallowed" in w
               for w in r["warnings"])
    # the inspected real pattern is used when allowed; cards are parsed
    page = FakePage({})
    r = _pw(page)
    assert page.visited[0] == ("https://www.yello.ae/category/"
                               "doctors-and-clinics/city:dubai")
    assert len(page.visited) <= PF.MAX_DIRECTORY_PAGES
    names = {c["company_name"] for c in r["companies"]}
    assert names == {"Smile Dental Clinic LLC", "Pearl Medical Centre"}
    smile = next(c for c in r["companies"] if c["company_name"].startswith(
        "Smile"))
    assert smile["phone_e164"] == "+97145550101" and smile["city"] == "Dubai"
    assert smile["email"] is None and smile["source"] == "playwright"
    # disabled sources are reported, never visited
    assert any("Connect AE skipped" in w for w in r["warnings"])


def test_find_via_playwright_stops_at_max_minutes():
    ticks = iter(range(0, 10_000, 360))               # +6 min per call
    page = FakePage({})
    r = _pw(page, max_minutes=10, clock=lambda: next(ticks))
    assert len(page.visited) == 1                      # 2nd page: 12 min
    assert r["pages_fetched"] == 1
    assert any("time_limit_reached" in w for w in r["warnings"])
    assert r["ok"] and len(r["companies"]) == 2        # what was collected


def test_find_via_playwright_does_not_bypass_login_wall():
    first = "https://www.yello.ae/category/doctors-and-clinics/city:dubai"
    for html, final, kind in (
            ("<html><head><title>Just a moment...</title></head>"
             "<body>challenge-platform</body></html>", first,
             "captcha_or_challenge"),
            ('<form><input type="email"><input type="password"></form>',
             first, "login_wall"),
            ("<html>please sign in</html>",
             "https://www.yello.ae/sign-in/?next=x", "login_wall")):
        page = FakePage({first: (200, html, final)})
        r = _pw(page)
        assert page.visited == [first]                 # stops right there
        assert r["companies"] == []
        assert any("%s (not bypassed)" % kind in w for w in r["warnings"])
    # Saudi Arabia: the only source (Maroof) is disabled, nothing is loaded
    page = FakePage({})
    r = PF.find_via_playwright("clinics", "SA", page_factory=_factory(page),
                               robots_fetcher=lambda u: ALLOW,
                               sleep=lambda s: None)
    assert page.visited == [] and any("Maroof SA skipped" in w
                                      for w in r["warnings"])


# ── shared ──

def test_normalize_email_lowercases_and_trims():
    assert PF.normalize_email("  Info@Clinic.AE. ") == "info@clinic.ae"
    assert PF.normalize_email("mailto:Sales@Clinic.ae?subject=hi") == \
        "sales@clinic.ae"
    for bad in ("", None, "not-an-email", "noreply@clinic.ae",
                "logo@2x.png", "x@sentry.io", "user@example.com"):
        assert PF.normalize_email(bad) is None, bad
    assert PF.normalize_phone("04 555 0101", "AE") == "+97145550101"
    assert PF.normalize_phone("0551234567", "SA") == "+966551234567"


def test_dedupe_companies_by_email_then_name_phone():
    rows = [
        {"company_name": "Smile", "email": "Info@Smile.ae", "phone_e164": None},
        {"company_name": "Smile Clinic", "email": "info@smile.ae",
         "phone_e164": "+97145550101"},                 # same email
        {"company_name": "Pearl", "email": None, "phone_e164": "+97142223333"},
        {"company_name": "PEARL", "email": None, "phone_e164": "+97142223333"},
        {"company_name": "Pearl", "email": None, "phone_e164": "+97149999999"},
    ]
    out = PF.dedupe_companies(rows)
    assert len(out) == 3
    assert out[0]["company_name"] == "Smile"           # first one wins
    assert out[0]["phone_e164"] == "+97145550101"      # gap filled
    assert [o["phone_e164"] for o in out[1:]] == ["+97142223333",
                                                  "+97149999999"]


def test_rank_company_prefers_role_email_and_sector_match():
    base = {"company_name": "Smile Dental Clinic", "sector": "clinics",
            "country": "AE", "phone_e164": "+97145550101",
            "website": "https://smile.ae"}
    role = dict(base, email="info@smile.ae")
    personal = dict(base, email="sara@smile.ae")
    off_sector = dict(role, company_name="Global Trading Co")
    assert PF.rank_company(role) == 100
    assert PF.rank_company(role) > PF.rank_company(personal)
    assert PF.rank_company(role) - PF.rank_company(off_sector) == 30
    assert PF.is_role_email("Contact@x.ae") and not PF.is_role_email("a@x.ae")
    assert PF.rank_company({}) == 0


# ── quality filters ──

def _co(**kw):
    """A clean UAE clinic; each test changes one thing."""
    base = {"company_name": "Smile Dental Clinic",
            "email": "info@smileclinic.ae", "phone_e164": "+97145550101",
            "website": "https://smileclinic.ae", "sector": "clinics",
            "country": "AE", "source": "serper",
            "source_url": "https://smileclinic.ae/contact",
            "confidence": "high"}
    base.update(kw)
    return base


def test_filter_blocks_scribd_domain():
    # a Scribd page as the source is a document
    kept, reason, _ = PF.screen_company(_co(
        source_url="https://www.scribd.com/document/1/Dubai-Clinics",
        website="https://scribd.com"), "AE")
    assert kept is None and reason == "document_source"
    # Scribd as the website or the email domain is a blocked domain
    for kw in ({"website": "https://www.scribd.com"},
               {"email": "info@scribd.com"}):
        kept, reason, _ = PF.screen_company(_co(**kw), "AE")
        assert kept is None and reason == "blocked_domain", kw
    assert "scribd.com" in PF.BLOCKED_DOMAINS


def test_filter_blocks_directory_domains():
    for d in ("ifind.ae", "sovereignwhale.com", "quanticdata.io",
              "desertcart.ae", "google.ae", "alwatan.ae", "yello.ae"):
        kept, reason, _ = PF.screen_company(_co(
            source_url="https://www.%s/listing/1" % d,
            website="https://%s" % d), "AE")
        assert kept is None and reason == "blocked_domain", d
    # subdomains are blocked too; matching is on a dot boundary
    assert PF._domain_blocked("dubai.ifind.ae")
    assert not PF._domain_blocked("fedex.com")       # not x.com
    assert not PF._domain_blocked("smileclinic.ae")


def test_filter_rejects_title_like_name_with_colon():
    for name in ("2026 Guide: Email Campaign for Dubai Dental Clinics",
                 "Get Expert Guidance On Citizenship And Residency At ...",
                 "About Us", "Home", "Clinics » Dubai", "Gulf News",
                 "www.smileclinic.ae", "https://smileclinic.ae", "x" * 71,
                 "A", "   "):
        kept, reason, _ = PF.screen_company(_co(company_name=name), "AE")
        assert kept is None and reason == "title_like_name", name
    # whole words only: "news" does not reject "Newstar"
    for name in ("Newstar Dental Clinic", "Smile Dental Clinic"):
        assert PF.screen_company(_co(company_name=name), "AE")[0], name


def test_filter_rejects_title_like_name_with_arabic_news_word():
    for name in ("رئيس الدولة والرئيس السوري يبحثان هاتفياً",
                 "أخبار العيادات في دبي", "من نحن", "دليل العيادات"):
        kept, reason, _ = PF.screen_company(_co(company_name=name), "AE")
        assert kept is None and reason == "title_like_name", name
    assert PF.screen_company(_co(company_name="عيادة الابتسامة"), "AE")[0]


def test_filter_keeps_company_with_llc_suffix():
    for name in ("Smile Dental Clinic LLC | Dubai",
                 "Al Noor Medical Centre FZ-LLC",
                 "Pearl Group: Clinics", "Gulf Holding — Clinics",
                 "Oasis Trading L.L.C", "Emirates Est. for Clinics"):
        kept, reason, _ = PF.screen_company(_co(company_name=name), "AE")
        assert kept and reason is None, name
        assert kept["company_name"] == name


def test_filter_clears_phone_with_wrong_country_code():
    kept, reason, notes = PF.screen_company(
        _co(company_name="Estheticare Clinic", phone_e164="+923001234567"),
        "AE")
    assert kept and reason is None                  # the company stays
    assert kept["phone_e164"] is None
    assert notes == ["phone_wrong_country: +923001234567"]
    # a UAE number is wrong in a Saudi run, and right in a UAE run
    kept, _, notes = PF.screen_company(_co(), "SA")
    assert kept["phone_e164"] is None and notes[0].startswith(
        "phone_wrong_country")
    kept, _, notes = PF.screen_company(_co(), "AE")
    assert kept["phone_e164"] == "+97145550101" and notes == []


def test_filter_marks_email_domain_mismatch_as_low_confidence():
    kept, _, notes = PF.screen_company(_co(
        email="movingservice953@gmail.com", website="https://anyrentals.ae"),
        "AE")
    assert kept["confidence"] == "low"
    assert notes == ["email_domain_mismatch: gmail.com vs anyrentals.ae"]
    assert kept["quality_warnings"] == notes
    kept, _, notes = PF.screen_company(_co(
        email="info@astons.com", website="https://astonsrealty.ae"), "AE")
    assert kept["confidence"] == "low" and notes
    # same base domain: a match, confidence untouched
    for email, site in (("info@dubaidentalrating.com",
                         "https://www.dubaidentalrating.com"),
                        ("info@mail.smileclinic.ae", "https://smileclinic.ae"),
                        ("info@smile.co.ae", "https://www.smile.co.ae")):
        kept, _, notes = PF.screen_company(_co(email=email, website=site),
                                           "AE")
        assert kept["confidence"] == "high" and notes == [], email
    # two firms under the same .co.ae second level are not a match
    assert PF.screen_company(_co(email="info@a.co.ae",
                                 website="https://b.co.ae"),
                             "AE")[0]["confidence"] == "low"


def test_filter_rejects_pdf_source():
    for url in ("https://smileclinic.ae/files/brochure.PDF",
                "https://smileclinic.ae/price-list.xlsx",
                "https://smileclinic.ae/docs/team.docx?dl=1"):
        kept, reason, _ = PF.screen_company(_co(source_url=url), "AE")
        assert kept is None and reason == "document_source", url


def test_filter_rejects_news_path_source():
    for url in ("https://smileclinic.ae/news/new-branch",
                "https://smileclinic.ae/en/blog/tips",
                "https://smileclinic.ae/press/2026",
                "https://smileclinic.ae/wp-content/uploads/2024/list.html",
                "https://smileclinic.ae/article/x"):
        kept, reason, _ = PF.screen_company(_co(source_url=url), "AE")
        assert kept is None and reason == "document_source", url
    assert PF.screen_company(_co(source_url="https://smileclinic.ae/"
                                 "newsletter"), "AE")[0]


def test_filter_marks_sector_mismatch():
    for name, url in (("Khalix", "https://khalix.ae/ai-automation"),
                      ("Deliver Technologies",
                       "https://deliver.ae/web-design-for-restaurants")):
        kept, reason, notes = PF.screen_company(_co(
            company_name=name, sector="restaurants", source_url=url,
            email=None, website="https://%s" % PF._host(url)), "AE")
        assert kept and reason is None                # soft: kept
        assert kept["sector"] == "unknown"
        assert notes == ["sector_mismatch: restaurants"]
    # a real restaurant, and a law firm offering "legal consulting", stay
    kept, _, notes = PF.screen_company(_co(
        sector="restaurants", email=None, website="https://alfanar.ae",
        source_url="https://alfanar.ae/menu"), "AE")
    assert kept["sector"] == "restaurants" and notes == []
    kept, _, _ = PF.screen_company(_co(
        sector="lawyers", email=None, website="https://hadef.ae",
        source_url="https://hadef.ae/legal-consulting"), "AE")
    assert kept["sector"] == "lawyers"


FILTER_ITEMS = [
    {"title": "Dubai Dental Clinics Email List",
     "link": "https://www.scribd.com/document/1/x",
     "snippet": "info@astons.com"},                          # document
    {"title": "About Us", "link": "https://goodclinic.ae/about",
     "snippet": "info@goodclinic.ae"},                        # title
    {"title": "Get Expert Guidance On Citizenship And Residency At ...",
     "link": "https://citizenship.ae/x",
     "snippet": "info@citizenship.ae"},                       # title
    {"title": "Smile Dental", "link": "https://www.ifind.ae/smile",
     "snippet": "info@smile.ae"},                             # blocked
    {"title": "Clinic list", "link": "https://dha-list.ae/files/c.pdf",
     "snippet": "no email here"},                             # document
    {"title": "Any Rentals", "link": "https://anyrentals.ae/",
     "snippet": "movingservice953@gmail.com"},                # kept, low
    {"title": "Real Clinic", "link": "https://realclinic.ae/",
     "snippet": "info@realclinic.ae"},                        # kept
]


def test_rejected_companies_counted_by_reason():
    f = Fetcher()
    r = _serper(Serper(default=FILTER_ITEMS), f)
    assert [c["website"] for c in r["companies"]] == [
        "https://realclinic.ae", "https://anyrentals.ae"]
    assert r["companies_rejected"] == {"title_like_name": 2,
                                       "blocked_domain": 1,
                                       "document_source": 2, "total": 5}
    assert r["companies_cleaned"] == {"phone_wrong_country": 0,
                                      "email_domain_mismatch": 1,
                                      "sector_mismatch": 0}
    for w in ("rejected:title_like_name: 2", "rejected:blocked_domain: 1",
              "rejected:document_source: 2"):
        assert w in r["warnings"], w
    assert "email_domain_mismatch: gmail.com vs anyrentals.ae" in \
        r["warnings"]
    reasons = {(x["company_name"], x["reason"])
               for x in r["rejected_companies"]}
    assert ("About Us", "title_like_name") in reasons
    assert ("Smile Dental", "blocked_domain") in reasons
    assert f.calls == []              # the PDF was never fetched
    # the same counts reach find_prospects and find_all_sectors
    kw = {"http_post": Serper(default=FILTER_ITEMS), "fetcher": Fetcher(),
          "sleep": lambda s: None}
    p = PF.find_prospects("clinics", "AE", 20, "serper", **kw)
    assert p["companies_rejected"] == r["companies_rejected"]
    assert p["companies_cleaned"] == r["companies_cleaned"]
    assert len(p["rejected_companies"]) == 5 and p["strict_filters"]
    a = PF.find_all_sectors(["clinics", "salons"], "AE", 20, "serper", **kw)
    assert a["companies_rejected"]["total"] == 10
    assert a["companies_rejected"]["title_like_name"] == 4
    assert a["companies_cleaned"]["email_domain_mismatch"] == 2
    assert [s["companies_rejected"]["total"] for s in a["sectors"]] == [5, 5]


def test_all_filters_off_when_strict_flag_false():
    f = Fetcher()
    r = _serper(Serper(default=FILTER_ITEMS), f, strict_filters=False)
    assert len(r["companies"]) == 6                  # old behaviour
    assert r["companies_rejected"]["total"] == 0
    assert all(v == 0 for v in r["companies_cleaned"].values())
    assert r["rejected_companies"] == []
    assert not any(w.startswith("rejected:") for w in r["warnings"])
    gmail = next(c for c in r["companies"]
                 if c["website"] == "https://anyrentals.ae")
    assert gmail["confidence"] == "medium" and "quality_warnings" not in gmail
    assert "https://dha-list.ae/files/c.pdf" in f.calls   # fetched, as before
    p = PF.find_prospects("clinics", "AE", 20, "serper", strict_filters=False,
                          http_post=Serper(default=FILTER_ITEMS),
                          fetcher=Fetcher(), sleep=lambda s: None)
    assert p["companies_found"] == 6 and not p["strict_filters"]
    assert p["companies_rejected"]["total"] == 0
