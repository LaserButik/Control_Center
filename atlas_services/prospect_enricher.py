# -*- coding: utf-8 -*-
"""ATLAS service: enrich prospects from their OWN public website.

For each company with a `website`, visit at most 3 same-host pages
(contact, about/team, homepage), read only what is publicly shown, and add:
email, emails_all, phones_all, decision_makers, social_links, address,
enriched_at, enrichment_status, enrichment_warnings.

Politeness and limits — enforced in code:
  - robots.txt fetched once per host (cached) and checked for our token
    "AIMentorsBot" (which falls back to the "*" group, as RFC 9309
    specifies). 4xx = no rules; 5xx / timeout = the whole host is skipped.
    It is always honoured: respect_robots=False is ignored, with a warning.
  - at most 3 page fetches per company, same host only (a redirect to
    another host is discarded), never an external link.
  - sleep_between_pages_s between pages of one host (raised to a longer
    robots.txt Crawl-delay, up to 30 s), sleep_between_companies_s between
    companies.
  - every request times out after timeout_s; bodies are capped at 1 MB.
  - requests only. No Playwright, proxies, stealth or CAPTCHA solving.
  - phone normalisation is a minimal local copy of outreach/phone_utils
    (that project is not imported).

Note: names of founders or managers are personal data (UAE PDPL, Saudi
PDPL) even on a public page — review before use.

CLI:
    python -m atlas_services.prospect_enricher --input prospects.json \\
        --out enriched.json --max 30 --delay 3
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

try:
    import requests
except ImportError:                      # the module still imports
    requests = None

UA = "Mozilla/5.0 (compatible; AIMentorsBot/1.0; +https://salehhaidar.com/bot)"
UA_TOKEN = "AIMentorsBot"
MAX_PAGES_PER_COMPANY = 3
MAX_BODY_BYTES = 1_000_000
MAX_CRAWL_DELAY_S = 30.0
HARD_MAX_COMPANIES = 100

CONTACT_PATHS = ("/contact", "/contact-us", "/contactus")
ABOUT_PATHS = ("/about", "/about-us", "/team", "/our-team", "/people")
_CONTACT_HINT = re.compile(r"contact|get-in-touch|reach-us|تواصل|اتصل", re.I)
_ABOUT_HINT = re.compile(r"about|team|people|leadership|management|"
                         r"who-we-are|من-نحن|فريق", re.I)

ROLE_LOCALS = ("noreply", "no-reply", "donotreply", "do-not-reply",
               "postmaster", "abuse", "mailer-daemon")
BLOCKED_EMAIL_DOMAINS = ("sentry.io", "wixpress.com", "example.com",
                         "example.org", "example.net", "sentry-next.wixpress.com")
ASSET_TLDS = ("png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "ico")
GENERIC_PREFERRED = ("info", "sales", "contact", "hello", "enquiries",
                     "enquiry", "inquiries", "office", "admin")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")

ROLES = ("Founder & CEO", "Founder and CEO", "Co-Founder & CEO",
         "Co-Founder", "Co-founder", "Founder", "Chief Executive Officer",
         "CEO", "Managing Director", "General Manager", "Medical Director",
         "Clinical Director", "Clinic Manager", "Managing Partner",
         "Owner", "Chairman", "President", "Director", "Partner",
         "Operations Manager", "Country Manager")
_ROLE_RX = "|".join(re.escape(r) for r in sorted(ROLES, key=len,
                                                 reverse=True))
_NAME_RX = (r"(?:(?:Dr|Mr|Ms|Mrs|Prof)\.?\s+)?"
            r"[A-Z][a-zA-Z'\-]+(?:\s+(?:al-|Al-|bin |Bin |El-)?"
            r"[A-Z][a-zA-Z'\-]+){1,3}")
NAME_STOPWORDS = {"our", "the", "about", "contact", "team", "meet", "read",
                  "more", "view", "profile", "learn", "us", "home", "services",
                  "dubai", "abu", "dhabi", "sharjah", "riyadh", "jeddah",
                  "healthcare", "city", "clinic", "center", "centre",
                  "medical", "group", "company", "llc", "fz", "fze",
                  "managing", "director", "general", "manager", "chief",
                  "executive", "officer", "founder", "ceo", "co"}

SOCIAL = {
    "linkedin": (re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/"
                            r"(company|school|showcase)/[^/?#\s]+", re.I),),
    "instagram": (re.compile(r"^https?://(www\.)?instagram\.com/"
                             r"(?!p/|reel/|reels/|explore|accounts|stories/)"
                             r"[A-Za-z0-9_.]+/?$", re.I),),
    "twitter": (re.compile(r"^https?://(www\.)?(twitter|x)\.com/"
                           r"(?!intent|share|home|hashtag|search|i/)"
                           r"[A-Za-z0-9_]{1,15}/?$", re.I),),
    "facebook": (re.compile(r"^https?://(www\.|m\.)?facebook\.com/"
                            r"(?!sharer|share|dialog|tr|plugins|profile\.php)"
                            r"[A-Za-z0-9.\-]+/?$", re.I),),
}

UAE_SA_CITIES = ("Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah",
                 "Fujairah", "Umm Al Quwain", "Al Ain", "Riyadh", "Jeddah",
                 "Dammam", "Khobar", "Mecca", "Makkah", "Medina", "Madinah")
_ADDRESS_HINT = re.compile(r"\b(P\.?\s?O\.?\s?Box|Building|Bldg|Tower|"
                           r"Street|St\.|Road|Rd\.|Floor|Office|Suite|Villa|"
                           r"Healthcare City|Business Bay|Plot)\b", re.I)


# ───────────────────────── HTML reading ─────────────────────────

_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3",
               "h4", "h5", "h6", "section", "article", "header", "footer",
               "address", "span", "strong", "b", "em", "small", "figcaption"}


class _Page(HTMLParser):
    """Anchors (href, text), visible text split into lines, JSON-LD."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.lines, self.jsonld = [], [], []
        self._buf, self._a, self._skip = [], None, 0
        self._script_ld = False
        self._ld_buf = []

    def _flush(self):
        line = " ".join("".join(self._buf).split())
        if line:
            self.lines.append(line)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict((k, v or "") for k, v in attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
            if tag == "script" and "ld+json" in a.get("type", "").lower():
                self._script_ld, self._ld_buf = True, []
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag == "a":
            self._a = [a.get("href", ""), []]

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self._skip = max(0, self._skip - 1)
            if tag == "script" and self._script_ld:
                self.jsonld.append("".join(self._ld_buf))
                self._script_ld = False
            return
        if tag == "a" and self._a is not None:
            self.links.append((self._a[0], " ".join("".join(self._a[1])
                                                     .split())))
            self._a = None
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            if self._script_ld:
                self._ld_buf.append(data)
            return
        self._buf.append(data)
        if self._a is not None:
            self._a[1].append(data)

    def close(self):
        super().close()
        self._flush()


def _parse(html: str) -> _Page:
    p = _Page()
    try:
        p.feed(html or "")
        p.close()
    except Exception:
        pass
    return p


# ───────────────────────── extractors (pure) ─────────────────────────

def _email_ok(e: str) -> bool:
    local, _, domain = e.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if local in ROLE_LOCALS or local.split("+")[0] in ROLE_LOCALS:
        return False
    if domain.rsplit(".", 1)[-1] in ASSET_TLDS:          # logo@2x.png
        return False
    return not any(domain == d or domain.endswith("." + d)
                   for d in BLOCKED_EMAIL_DOMAINS)


def extract_emails(html: str) -> list[str]:
    """Deduped, lowercased; mailto: links first, then plain text."""
    page = _parse(html)
    found = []
    for href, _ in page.links:
        if href.lower().startswith("mailto:"):
            addr = htmllib.unescape(href[7:].split("?")[0]).strip()
            found.append(addr)
    text = htmllib.unescape(html or "")
    text = re.sub(r"\s*(\[at\]|\(at\))\s*", "@", text, flags=re.I)
    found += _EMAIL.findall(text)
    out = []
    for e in found:
        e = e.strip().strip(".,;:").lower()
        if _EMAIL.fullmatch(e) and _email_ok(e) and e not in out:
            out.append(e)
    return out


# --- minimal local copy of outreach/phone_utils.to_e164 (not imported) ---
_CODES = {"AE": "971", "SA": "966"}


def _to_e164(phone: str, default_country: str = "AE") -> str | None:
    s = re.sub(r"[\s\-().\u200e\u200f]", "", str(phone or ""))
    if s.lower().startswith("tel:"):
        s = s[4:]
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+"):
        d = s[1:]
        return s if d.isdigit() and 10 <= len(d) <= 15 else None
    if not s.isdigit():
        return None
    for code in _CODES.values():
        if s.startswith(code) and 8 <= len(s) - len(code) <= 9:
            return "+" + s
    code = _CODES.get((default_country or "").upper())
    if code and 9 <= len(s) <= 10:
        nat = s[1:] if s.startswith("0") else s
        if 8 <= len(nat) <= 9 and not nat.startswith("0"):
            return "+" + code + nat
    return None


_PHONE_TEXT = re.compile(
    r"(?:\+|00)\s?(?:971|966)[\s\-.]?\(?\d{1,2}\)?[\s\-.]?\d{3}[\s\-.]?\d{3,4}"
    r"|\b0(?:5\d|[1-4679])[\s\-.]?\d{3}[\s\-.]?\d{3,4}\b")


def extract_phones(html: str, default_country: str = "AE") -> list[str]:
    """Deduped E.164 numbers from tel: links, then UAE/SA text patterns."""
    page = _parse(html)
    raw = [h[4:] for h, _ in page.links if h.lower().startswith("tel:")]
    raw += _PHONE_TEXT.findall(" ".join(page.lines))
    out = []
    for r in raw:
        e = _to_e164(r, default_country)
        if e and e not in out:
            out.append(e)
    return out


def _clean_name(name: str) -> str | None:
    name = " ".join(name.split()).strip(" ,-|:")
    words = [w.strip(".,") for w in name.split()]
    core = [w for w in words if w.lower().rstrip(".") not in
            ("dr", "mr", "ms", "mrs", "prof")]
    if not 2 <= len(core) <= 4:
        return None
    if any(w.lower().strip("-") in NAME_STOPWORDS for w in core):
        return None
    return name


def extract_decision_makers(html: str) -> list[dict]:
    """Confident {name, role} pairs: "Name, Role", "Name - Role",
    "Name (Role)", "Role: Name", or a name line directly followed by a
    role line. [] when nothing is confident."""
    lines = _parse(html).lines
    out, seen = [], set()

    def add(name, role):
        n = _clean_name(name)
        if not n:
            return
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append({"name": n, "role": role.strip()})

    pats = [
        re.compile(r"(?P<name>%s)\s*(?:,|–|—|-|\||\()\s*(?P<role>%s)\b"
                   % (_NAME_RX, _ROLE_RX)),
        re.compile(r"\b(?P<role>%s)\s*(?::|–|—|-|\|)\s*(?P<name>%s)"
                   % (_ROLE_RX, _NAME_RX)),
    ]
    for line in lines:
        if len(line) > 160:
            continue
        for rx in pats:
            for m in rx.finditer(line):
                add(m.group("name"), m.group("role"))
    full_role = re.compile(r"^(?:%s)$" % _ROLE_RX, re.I)
    full_name = re.compile(r"^%s$" % _NAME_RX)
    for a, b in zip(lines, lines[1:]):
        if full_name.match(a) and full_role.match(b):
            role = next((r for r in ROLES if r.lower() == b.lower()), b)
            add(a, role)
    return out


def extract_social_links(html: str) -> dict:
    """Company pages only: LinkedIn /company/ (never /in/ profiles), and the
    site's own Instagram / X / Facebook page links (share buttons and post
    links are excluded)."""
    out = {k: None for k in SOCIAL}
    for href, _ in _parse(html).links:
        url = href.strip().split("?")[0].split("#")[0]
        for key, (rx,) in SOCIAL.items():
            if out[key] is None and rx.match(url):
                out[key] = url.rstrip("/")
    return out


def _jsonld_address(blocks: list[str]) -> str:
    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if t == "PostalAddress" or (isinstance(t, list)
                                        and "PostalAddress" in t):
                parts = [node.get(k) for k in ("streetAddress",
                                               "addressLocality",
                                               "addressRegion",
                                               "postalCode",
                                               "addressCountry")]
                parts = [p if isinstance(p, str) else (p or {}).get("name")
                         for p in parts]
                text = ", ".join(p.strip() for p in parts if p and
                                 isinstance(p, str) and p.strip())
                if text:
                    return text
            for v in node.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = walk(v)
                if r:
                    return r
        return ""
    for b in blocks:
        try:
            r = walk(json.loads(b))
        except ValueError:
            continue
        if r:
            return r
    return ""


def extract_address(html: str) -> str:
    """schema.org PostalAddress first, then a short line with an address
    word (P.O. Box, Building, Street, Floor…) and a UAE/SA city. ""."""
    page = _parse(html)
    found = _jsonld_address(page.jsonld)
    if found:
        return found[:200]
    best = ""
    for line in page.lines:
        if len(line) > 200 or not _ADDRESS_HINT.search(line):
            continue
        if not any(c.lower() in line.lower() for c in UAE_SA_CITIES):
            continue
        if not best or len(line) < len(best):
            best = line
    return best


# ───────────────────────── network ─────────────────────────

def http_get(url: str, timeout_s: float = 10) -> tuple:
    """(status, text|None, final_url). Body capped at 1 MB; non-HTML bodies
    return text None. HTTP errors return their status; network failures
    raise. Never used by tests."""
    if requests is None:
        raise RuntimeError("requests not installed")
    deadline = time.monotonic() + timeout_s
    with requests.get(url, headers={"User-Agent": UA}, timeout=timeout_s,
                      stream=True, allow_redirects=True) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        if r.status_code >= 400 or not ("html" in ctype or "text" in ctype
                                        or not ctype):
            return r.status_code, None, r.url
        chunks, size = [], 0
        for chunk in r.iter_content(65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BODY_BYTES or time.monotonic() > deadline:
                break                        # truncate silently
        body = b"".join(chunks)[:MAX_BODY_BYTES]
        return r.status_code, body.decode(r.encoding or "utf-8",
                                          "replace"), r.url


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h



def _base(website: str) -> str | None:
    w = (website or "").strip()
    if not w:
        return None
    if "://" not in w:
        w = "https://" + w
    s = urlsplit(w)
    if s.scheme not in ("http", "https") or not s.hostname:
        return None
    return "%s://%s" % (s.scheme, s.netloc)


class _Session:
    """Shared state for one run: fetcher, robots cache, page cache,
    counters."""

    def __init__(self, fetcher=None, timeout_s: float = 10):
        self._fetch = fetcher or (lambda u: http_get(u, timeout_s))
        self.robots = {}            # host -> (RobotFileParser|None, err)
        self.pages = {}             # url -> (status, text, final_url)
        self.network_calls = 0

    def get(self, url: str):
        if url in self.pages:
            return self.pages[url]
        self.network_calls += 1
        try:
            res = self._fetch(url)
        except Exception as e:
            res = (None, None, url, type(e).__name__)
        res = tuple(res)
        if len(res) == 2:                   # test fetchers: (status, text)
            res = (res[0], res[1], url)
        self.pages[url] = res
        return res

    def robots_for(self, base: str):
        host = _host(base)
        if host not in self.robots:
            status, text, _final = self.get(base + "/robots.txt")[:3]
            if status is None or status >= 500:
                self.robots[host] = (None, "robots_unreachable")
            else:
                rp = RobotFileParser()
                rp.parse((text or "").splitlines()
                         if 200 <= status < 300 else [])     # 4xx: no rules
                self.robots[host] = (rp, None)
        return self.robots[host]


def find_contact_pages(base_url: str, fetcher, sleep) -> list[str]:
    """Candidate URLs in priority order: a contact page, an about/team page,
    then the homepage last. Uses links actually present on the homepage
    when there are any (same host only), else the standard paths. Each URL
    is normalised and deduplicated. `fetcher(url)` returns
    (status, text[, final_url]); the homepage is read once."""
    base = _base(base_url)
    if not base:
        return []
    home = base + "/"
    try:
        res = tuple(fetcher(home))
    except Exception:
        res = (None, None)
    html = res[1] if len(res) > 1 and res[0] == 200 else ""
    host = _host(base)
    contact, about = [], []
    for href, text in _parse(html).links:
        url = urljoin(home, href).split("#")[0].split("?")[0]
        if not url.startswith(("http://", "https://")) or \
                _host(url) != host:
            continue                         # never an external link
        path = urlsplit(url).path.lower()
        blob = path + " " + (text or "").lower()
        if _CONTACT_HINT.search(blob) and url not in contact:
            contact.append(url)
        elif _ABOUT_HINT.search(blob) and url not in about:
            about.append(url)
    contact = contact or [base + p for p in CONTACT_PATHS]
    about = about or [base + p for p in ABOUT_PATHS]
    out = []
    for u in contact + about + [home]:
        u = u.rstrip("/") + ("/" if u.rstrip("/") == base else "")
        if u not in out and u != home:
            out.append(u)
    out.append(home)                         # always last
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _blank(company: dict) -> dict:
    c = dict(company or {})
    c.update(email=c.get("email") or None, emails_all=[], phones_all=[],
             decision_makers=[], social_links={k: None for k in SOCIAL},
             address="", enriched_at=_now(), enrichment_status="skipped",
             enrichment_warnings=[])
    return c


def _choose_email(emails: list[str], website_host: str) -> str | None:
    if not emails:
        return None
    own = [e for e in emails if _host("https://" + e.split("@")[1])
           == website_host]
    pool = own or emails
    for pref in GENERIC_PREFERRED:
        for e in pool:
            if e.split("@")[0] == pref:
                return e
    return pool[0]


# ───────────────────────── public API ─────────────────────────

def enrich_prospect(company: dict, *, timeout_s: int = 10,
                    respect_robots: bool = True,
                    sleep_between_pages_s: float = 2.0,
                    sleep=time.sleep, fetcher=None,
                    _session: _Session | None = None) -> dict:
    """Enrich one company. Never raises; always returns a dict. `fetcher`
    (url -> (status, text[, final_url])) replaces the network in tests."""
    c = _blank(company)
    try:
        sess = _session or _Session(fetcher, timeout_s)
        if not respect_robots:
            c["enrichment_warnings"].append(
                "respect_robots=False ignored: robots.txt is always "
                "honoured")
        base = _base(c.get("website") or "")
        if not base:
            c["enrichment_warnings"].append("enrichment_skipped: no_website")
            return c
        host = _host(base)
        rp, err = sess.robots_for(base)
        if err:
            c["enrichment_warnings"].append("enrichment_skipped: %s" % err)
            return c
        delay = max(0.0, float(sleep_between_pages_s))
        cd = rp.crawl_delay(UA_TOKEN) if rp else None
        if cd and float(cd) > MAX_CRAWL_DELAY_S:
            c["enrichment_warnings"].append(
                "enrichment_skipped: crawl_delay_too_long")
            return c
        if cd:
            delay = max(delay, float(cd))

        def allowed(u):
            return rp is None or rp.can_fetch(UA_TOKEN, u)

        fetched = [0]                  # real page fetches for this company

        def polite_get(u):
            """Robots-checked, budgeted, delayed. Cached pages are free."""
            if not allowed(u):
                return (None, None, u)
            if u in sess.pages:
                return sess.pages[u]
            if fetched[0] >= MAX_PAGES_PER_COMPANY:
                return (None, None, u)
            if fetched[0] and delay:
                sleep(delay)
            fetched[0] += 1
            return sess.get(u)

        home = base + "/"
        candidates = find_contact_pages(base, polite_get, sleep)
        if allowed(home):
            status = sess.pages.get(home, (None,))[0]
            if status is None or status >= 400:
                c["enrichment_warnings"].append("enrichment_skipped: "
                                                "unreachable")
                return c

        def kind(u):
            path = urlsplit(u).path.rstrip("/")
            return "home" if not path else (
                "contact" if _CONTACT_HINT.search(path) else "about")

        # alternate contact / about so 3 pages cover both, homepage last
        groups = {"contact": [], "about": [], "home": []}
        for u in candidates:
            groups[kind(u)].append(u)
        order = []
        for pair in zip(groups["contact"] + [None] * 9,
                        groups["about"] + [None] * 9):
            order += [u for u in pair if u]
        order += groups["home"]

        emails, phones, people, social, address = [], [], [], {}, ""
        visited, done, blocked = [], set(), 0
        for url in order:
            k = kind(url)
            if k in done and k != "home":
                continue                   # already have this kind of page
            if not allowed(url):
                blocked += 1
                c["enrichment_warnings"].append(
                    "robots_disallowed: %s" % (urlsplit(url).path or "/"))
                continue
            status, html, final = polite_get(url)[:3]
            if status != 200 or not html:
                continue
            if _host(final or url) != host:
                c["enrichment_warnings"].append("redirected_off_host")
                continue
            visited.append(url)
            done.add(k)
            for e in extract_emails(html):
                if e not in emails:
                    emails.append(e)
            for p in extract_phones(html, c.get("country") or "AE"):
                if p not in phones:
                    phones.append(p)
            for d in extract_decision_makers(html):
                if d["name"].lower() not in {x["name"].lower()
                                             for x in people}:
                    people.append(d)
            for sk, sv in extract_social_links(html).items():
                if sv and not social.get(sk):
                    social[sk] = sv
            address = address or extract_address(html)
        c.update(emails_all=emails, phones_all=phones,
                 decision_makers=people,
                 social_links={k: social.get(k) for k in SOCIAL},
                 address=address, pages_visited=visited,
                 pages_fetched=fetched[0])
        c["email"] = c.get("email") or _choose_email(emails, host)
        if not emails:
            c["enrichment_warnings"].append("enrichment_warning: "
                                            "no_email_found")
        got_other = bool(phones or people or address
                         or any(social.values()))
        if emails:
            c["enrichment_status"] = "ok"
        elif got_other:
            c["enrichment_status"] = "partial"
        else:
            c["enrichment_status"] = "skipped"
            why = ("robots_disallowed" if blocked and not visited else
                   "unreachable" if not visited else "no_contact_info")
            c["enrichment_warnings"].append("enrichment_skipped: %s" % why)
        return c
    except Exception as e:                       # never raise
        c["enrichment_status"] = "skipped"
        c["enrichment_warnings"].append("error:%s" % type(e).__name__)
        return c


def enrich_many(companies: list, *, max_companies: int = 50,
                out_path: str | None = None,
                sleep_between_companies_s: float = 3.0, fetcher=None,
                sleep=time.sleep, timeout_s: int = 10,
                sleep_between_pages_s: float = 2.0, dry_run: bool = False,
                on_progress=None) -> dict:
    """Enrich up to max_companies (hard cap 100). dry_run=True makes no
    request: it only reports which companies have a website. on_progress
    (done, total, result) is called after each company."""
    t0 = time.perf_counter()
    rows = [c for c in (companies or []) if isinstance(c, dict)]
    cap = max(0, min(int(max_companies), HARD_MAX_COMPANIES))
    todo = rows[:cap]
    sess = _Session(fetcher, timeout_s)
    results, reasons = [], {}
    fetched_any = False
    for i, comp in enumerate(todo):
        if dry_run:
            r = _blank(comp)
            base = _base(r.get("website") or "")
            r["enrichment_status"] = "dry_run" if base else "skipped"
            r["enrichment_warnings"].append(
                "dry_run: would visit %s" % base if base
                else "enrichment_skipped: no_website")
        else:
            needs_net = bool(_base(comp.get("website") or ""))
            if needs_net and fetched_any and sleep_between_companies_s:
                sleep(max(0.0, float(sleep_between_companies_s)))
            r = enrich_prospect(comp, timeout_s=timeout_s,
                                sleep_between_pages_s=sleep_between_pages_s,
                                sleep=sleep, _session=sess)
            fetched_any = fetched_any or needs_net
        if r["enrichment_status"] == "skipped":
            why = next((w.split(": ", 1)[1] for w in
                        r["enrichment_warnings"]
                        if w.startswith("enrichment_skipped: ")), "other")
            reasons[why] = reasons.get(why, 0) + 1
        results.append(r)
        if on_progress:
            try:
                on_progress(i + 1, len(todo), r)
            except Exception:
                pass
    counts = {s: sum(1 for r in results if r["enrichment_status"] == s)
              for s in ("ok", "partial", "skipped", "dry_run")}
    out = {"ok": True, "processed": len(results), "enriched": counts["ok"],
           "partial": counts["partial"], "skipped": counts["skipped"],
           "dry_run": counts["dry_run"], "skipped_reasons": reasons,
           "network_calls": sess.network_calls,
           "duration_ms": int((time.perf_counter() - t0) * 1000),
           "not_processed": max(0, len(rows) - len(todo)),
           "results": results, "out_path": None}
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v for k, v in out.items() if k != "results"}
        payload.update(generated_at=_now(), results=results,
                       out_path=str(p))
        p.write_bytes(json.dumps(payload, ensure_ascii=False,
                                 indent=1).encode("utf-8"))
        out["out_path"] = str(p)
    return out


def load_companies(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("prospects", data.get("results", data)) \
        if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict) and not r.get("skipped")]


def summary_text(r: dict) -> str:
    lines = ["PROSPECT ENRICHMENT",
             "total companies ..... %s" % r["processed"],
             "enriched (email) .... %s" % r["enriched"],
             "partial ............. %s" % r["partial"],
             "skipped ............. %s %s" % (r["skipped"],
                                              r["skipped_reasons"] or ""),
             "network calls ....... %s" % r["network_calls"],
             "duration ............ %s ms" % r["duration_ms"],
             "output .............. %s" % (r["out_path"] or "(not written)")]
    if r.get("dry_run"):
        lines.insert(4, "dry run (no fetch) .. %s" % r["dry_run"])
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.prospect_enricher")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        companies = load_companies(a.input)
    except (OSError, ValueError) as e:
        sys.stdout.write("STOPPED: cannot read %s (%s)\n"
                         % (a.input, type(e).__name__))
        return 1
    r = enrich_many(companies, max_companies=a.max, out_path=a.out,
                    sleep_between_companies_s=max(2.0, a.delay),
                    dry_run=a.dry_run)
    text = summary_text(r)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
