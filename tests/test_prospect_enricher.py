# -*- coding: utf-8 -*-
"""ATLAS prospect enricher. A fake fetcher serves fixture HTML; sockets are
refused, so any real network attempt fails the test."""

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import prospect_enricher as PE      # noqa: E402

SITE = "https://clinic.ae"
ALLOW = (200, "User-agent: *\nAllow: /\n")

HOME = """<html><body>
<nav><a href="/contact-us">Contact</a><a href="/about">About us</a>
<a href="https://other-site.com/partners">Partners</a></nav>
<h1>Smile Clinic Dubai</h1>
<footer>
<p>Call us: +971 4 555 0101</p><p>Email: info@clinic.ae</p>
<a href="https://www.linkedin.com/company/smile-clinic-dubai/">LinkedIn</a>
<a href="https://www.linkedin.com/in/some-person-123">Our founder</a>
<a href="https://www.instagram.com/smileclinicdxb/">Instagram</a>
<a href="https://twitter.com/intent/tweet?url=x">Share</a>
<a href="https://x.com/SmileClinicDXB">X</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
<a href="https://www.facebook.com/SmileClinicDubai">Facebook</a>
<img src="/img/logo@2x.png">
</footer></body></html>"""

CONTACT = """<html><body>
<a href="mailto:Sales@Clinic.ae?subject=Hi">Sales@Clinic.ae</a>
<a href="mailto:noreply@clinic.ae">x</a>
<a href="tel:+971 4 555 0102">Call</a>
<p>Reach the front desk on 04-555-0103</p>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"MedicalClinic","address":{"@type":"PostalAddress",
"streetAddress":"Building 64, Dubai Healthcare City",
"addressLocality":"Dubai","addressCountry":"AE"}}</script>
</body></html>"""

ABOUT = """<html><body>
<h2>Our Team</h2>
<p>Dr. Sara Haddad, Founder &amp; CEO</p>
<h3>Omar Khalid</h3><p>Medical Director</p>
<p>Read More</p><p>Managing Director</p>
</body></html>"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


class Fetcher:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url):
        self.calls.append(url)
        v = self.pages.get(url, (404, None))
        if isinstance(v, Exception):
            raise v
        return v


def _site(robots=ALLOW, **override):
    pages = {SITE + "/robots.txt": robots, SITE + "/": (200, HOME),
             SITE + "/contact-us": (200, CONTACT),
             SITE + "/about": (200, ABOUT)}
    pages.update(override)
    return pages


def test_extract_emails_from_mailto_links():
    assert PE.extract_emails(CONTACT) == ["sales@clinic.ae"]
    assert PE.extract_emails('<a href="mailto:team&#64;clinic.ae">m</a>') \
        == ["team@clinic.ae"]


def test_extract_emails_dedupes_and_lowercases():
    html = ('<a href="mailto:Info@Clinic.AE">Info@Clinic.AE</a>'
            "<p>INFO@clinic.ae or info@clinic.ae. Also info [at] clinic.ae"
            "</p><p>Billing: Billing@Clinic.ae</p>")
    assert PE.extract_emails(html) == ["info@clinic.ae",
                                       "billing@clinic.ae"]


def test_extract_emails_excludes_role_addresses():
    html = ("noreply@clinic.ae no-reply@clinic.ae postmaster@clinic.ae "
            "abuse@clinic.ae mailer-daemon@clinic.ae "
            "605a7baede844d278b89dc95ae0a9123@sentry.io "
            "user@sentry-next.wixpress.com test@example.com "
            "logo@2x.png icon@3x.webp hello@clinic.ae")
    assert PE.extract_emails(html) == ["hello@clinic.ae"]


def test_extract_phones_uae_from_tel_link():
    assert PE.extract_phones('<a href="tel:+971 4 555 0102">c</a>') == \
        ["+97145550102"]
    assert PE.extract_phones('<a href="tel:0501234567">m</a>') == \
        ["+971501234567"]


def test_extract_phones_dedupes_and_normalizes():
    html = ('<a href="tel:+971501234567">a</a><p>Mobile 050 123 4567, '
            "landline 04-555-0103, intl 00971 4 555 0103, "
            "KSA +966 11 555 0101</p>")
    assert PE.extract_phones(html) == ["+971501234567", "+97145550103",
                                       "+966115550101"]
    assert PE._to_e164("+") is None and PE._to_e164("12345") is None


def test_extract_decision_makers_finds_ceo_pattern():
    people = PE.extract_decision_makers(ABOUT)
    assert {"name": "Dr. Sara Haddad", "role": "Founder & CEO"} in people
    assert {"name": "Omar Khalid", "role": "Medical Director"} in people
    # headings and stray role words are not mistaken for people
    assert all(p["name"] not in ("Our Team", "Read More") for p in people)
    assert len(people) == 2
    assert PE.extract_decision_makers("<p>Welcome to our clinic.</p>") == []


def test_extract_social_links_company_linkedin():
    s = PE.extract_social_links(HOME)
    assert s["linkedin"] == \
        "https://www.linkedin.com/company/smile-clinic-dubai"   # not /in/
    assert s["instagram"] == "https://www.instagram.com/smileclinicdxb"
    assert s["twitter"] == "https://x.com/SmileClinicDXB"        # no intent
    assert s["facebook"] == "https://www.facebook.com/SmileClinicDubai"
    only_person = '<a href="https://linkedin.com/in/jane-doe">Jane</a>'
    assert PE.extract_social_links(only_person)["linkedin"] is None


def test_enrich_skips_when_no_website():
    f = Fetcher({})
    r = PE.enrich_prospect({"company_name": "No Site LLC", "website": None,
                            "phone_e164": "+971501234567"}, fetcher=f,
                           sleep=lambda s: None)
    assert f.calls == []                         # no request at all
    assert r["enrichment_status"] == "skipped"
    assert "enrichment_skipped: no_website" in r["enrichment_warnings"]
    assert r["phone_e164"] == "+971501234567"    # original fields kept
    for key in ("email", "emails_all", "phones_all", "decision_makers",
                "social_links", "address", "enriched_at"):
        assert key in r


def test_enrich_respects_robots_disallow():
    # disallow everything for everyone: only robots.txt is fetched
    f = Fetcher(_site(robots=(200, "User-agent: *\nDisallow: /\n")))
    r = PE.enrich_prospect({"company_name": "C", "website": SITE},
                           fetcher=f, sleep=lambda s: None)
    assert f.calls == [SITE + "/robots.txt"]
    assert r["enrichment_status"] == "skipped"
    assert "enrichment_skipped: robots_disallowed" in \
        r["enrichment_warnings"]
    # a group for our own token: /contact-us is off-limits, the rest is not
    f = Fetcher(_site(robots=(200, "User-agent: AIMentorsBot\n"
                                   "Disallow: /contact-us\n")))
    r = PE.enrich_prospect({"company_name": "C", "website": SITE},
                           fetcher=f, sleep=lambda s: None)
    assert SITE + "/contact-us" not in f.calls
    assert r["email"] == "info@clinic.ae"        # from the homepage footer
    # robots.txt unreachable (5xx / timeout): the whole host is skipped
    for robots in ((503, None), TimeoutError("t")):
        f = Fetcher(_site(robots=robots))
        r = PE.enrich_prospect({"company_name": "C", "website": SITE},
                               fetcher=f, sleep=lambda s: None)
        assert f.calls == [SITE + "/robots.txt"]
        assert "enrichment_skipped: robots_unreachable" in \
            r["enrichment_warnings"]
    # a missing robots.txt (404) means no rules
    f = Fetcher(_site(robots=(404, None)))
    r = PE.enrich_prospect({"company_name": "C", "website": SITE},
                           fetcher=f, sleep=lambda s: None)
    assert r["enrichment_status"] == "ok"


def test_enrich_many_uses_injected_fetcher(tmp_path):
    f = Fetcher(_site())
    sleeps = []
    out = tmp_path / "enrichment" / "enriched.json"
    companies = [{"company_name": "Smile Clinic", "website": "clinic.ae"},
                 {"company_name": "No Site LLC", "website": None},
                 {"company_name": "Down Co", "website": "down.ae"},
                 {"company_name": "Beyond cap", "website": "x.ae"}]
    r = PE.enrich_many(companies, max_companies=3, out_path=str(out),
                       fetcher=f, sleep=sleeps.append,
                       sleep_between_companies_s=3.0,
                       sleep_between_pages_s=2.0)
    assert (r["processed"], r["enriched"], r["skipped"]) == (3, 1, 2)
    assert r["not_processed"] == 1 and not any("x.ae" in u for u in f.calls)
    assert r["skipped_reasons"] == {"no_website": 1, "unreachable": 1}
    smile = r["results"][0]
    assert smile["email"] == "info@clinic.ae"          # generic preferred
    # pages are read contact page first, homepage last
    assert smile["emails_all"] == ["sales@clinic.ae", "info@clinic.ae"]
    assert smile["phones_all"] == ["+97145550102", "+97145550103",
                                   "+97145550101"]
    assert smile["enrichment_status"] == "ok"
    assert smile["pages_visited"] == [SITE + "/contact-us", SITE + "/about",
                                      SITE + "/"]
    assert smile["address"] == ("Building 64, Dubai Healthcare City, Dubai, "
                                "AE")
    assert smile["social_links"]["linkedin"].endswith("/smile-clinic-dubai")
    assert {"name": "Dr. Sara Haddad", "role": "Founder & CEO"} in \
        smile["decision_makers"]
    # politeness: <= 3 pages per company, robots first, same host only
    clinic_calls = [u for u in f.calls if "clinic.ae" in u]
    assert clinic_calls[0] == SITE + "/robots.txt"
    assert len(clinic_calls) - 1 <= PE.MAX_PAGES_PER_COMPANY
    assert not any("other-site.com" in u for u in f.calls)
    assert 2.0 in sleeps and 3.0 in sleeps             # page + company gaps
    assert r["network_calls"] == len(f.calls)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["processed"] == 3 and len(data["results"]) == 3
    assert r["out_path"] == str(out)
    # dry run: no request at all
    f2 = Fetcher(_site())
    d = PE.enrich_many(companies, dry_run=True, fetcher=f2,
                       sleep=lambda s: None)
    assert f2.calls == [] and d["network_calls"] == 0 and d["dry_run"] == 3
