# -*- coding: utf-8 -*-
"""ATLAS service: find NEW prospects for 5 sectors in the GCC."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "prospects"
SEEN_FILE = DEFAULT_OUT_DIR / "seen.json"

SECTORS = {
    "clinics": {
        "en": [
            "dental clinic", "medical clinic", "dental center",
            "orthodontist", "dermatology clinic", "pediatric clinic",
            "cosmetic clinic", "physiotherapy clinic", "eye clinic",
            "dental implant", "teeth whitening", "fertility clinic",
            "gynecology clinic", "ENT clinic",
        ],
        "ar": ["عيادة جلدية", "مركز طبي", "عيادة طبية", "عيادة أسنان"]
    },
    "real_estate": {
        "en": [
            "real estate agency", "real estate broker", "property management",
            "property developer", "real estate consultant", "villa for sale",
            "apartment rental", "commercial property", "off-plan property",
            "real estate investment", "property finder", "rental agency",
            "holiday homes", "short term rental",
        ],
        "ar": ["إدارة أمالك", "وسيط عقاري", "وكالة عقارية"]
    },
    "restaurants": {
        "en": [
            "restaurant", "cafe", "coffee shop", "bakery",
            "catering company", "fine dining", "italian restaurant",
            "arabic restaurant", "japanese restaurant", "indian restaurant",
            "seafood restaurant", "burger joint", "pizza place",
            "shisha lounge", "breakfast restaurant",
        ],
        "ar": ["مطعم", "مقهى", "مخبز", "تموين"]
    },
    "salons": {
        "en": [
            "beauty salon", "hair salon", "barbershop", "nail salon",
            "spa", "massage center", "lash extensions", "brow studio",
            "makeup artist", "laser hair removal", "skin care clinic",
            "bridal makeup", "men's grooming", "hair treatment",
        ],
        "ar": ["صالون تجميل", "صالون حلاقة", "سبا", "مساج"]
    },
    "lawyers": {
        "en": [
            "law firm", "lawyer office", "legal consultant", "legal advisor",
            "corporate lawyer", "family lawyer", "criminal lawyer",
            "real estate lawyer", "immigration lawyer", "IP lawyer",
            "arbitration", "notary public", "legal services",
            "business lawyer", "contract lawyer",
        ],
        "ar": ["مكتب محاماة", "مستشار قانوني", "خدمات قانونية"]
    },
}

CITIES_AE = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]
CITIES_SA = ["Riyadh", "Jeddah", "Dammam", "Makkah", "Madinah", "Khobar"]
CITIES_QA = ["Doha", "Al Rayyan", "Al Wakrah"]
CITIES_KW = ["Kuwait City", "Hawalli", "Salmiya"]
CITIES_OM = ["Muscat", "Salalah", "Sohar"]
CITIES_BH = ["Manama", "Muharraq", "Riffa"]

CITIES = {
    "AE": CITIES_AE, "SA": CITIES_SA, "QA": CITIES_QA,
    "KW": CITIES_KW, "OM": CITIES_OM, "BH": CITIES_BH,
}

SERPER_URL = "https://google.serper.dev/search"
SERPER_ACCOUNT_URL = "https://google.serper.dev/account"
QUERIES_PER_SECTOR = 5
MAX_SERPER_CALLS_PER_RUN = 30
MAX_PAGES_PER_RUN = 40
MAX_DIRECTORY_PAGES = 3
PAGE_TIMEOUT_S = 10
PAGE_MAX_BYTES = 500_000
UA = "Mozilla/5.0 (compatible; AIMentorsBot/1.0; +https://salehhaidar.com/bot)"
UA_TOKEN = "AIMentorsBot"

SKIP_DOMAINS = {
    "facebook.com", "linkedin.com", "instagram.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "pinterest.com", "yellowpages.com", "yelp.com",
    "tripadvisor.com", "google.com", "wikipedia.org",
    "crunchbase.com",
}

ROLE_PREFIXES = {"info", "sales", "contact", "admin", "office"}
JUNK_LOCALS = {"noreply", "no-reply", "donotreply", "postmaster", "abuse", "mailer-daemon"}
JUNK_EMAIL_DOMAINS = {"sentry.io", "wixpress.com", "example.com", "example.org", "domain.com", "email.com"}
ASSET_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js"}

DIRECTORY_SOURCES = [
    {
        "name": "Yello UAE", "base": "https://www.yello.ae", "country": "AE",
        "search_path": "/category/{slug}/city:{city}",
        "page_suffix": "/{page}",
        "slugs": {
            "clinics": "doctors-and-clinics",
            "real_estate": "estate-agents",
            "restaurants": "restaurants",
            "salons": "beauty-salons",
            "lawyers": "lawyers",
        },
        "card_class": "company", "requires_robots_check": True,
        "enabled": True, "verified": "2026-10-07",
    },
    {
        "name": "Connect AE", "base": "https://www.connect.ae",
        "country": "AE", "search_path": "/search?q={query}&city={city}",
        "requires_robots_check": True, "enabled": False,
        "disabled_reason": "domain does not resolve",
    },
    {
        "name": "Maroof SA", "base": "https://maroof.sa", "country": "SA",
        "search_path": "/businesses?q={query}&city={city}",
        "requires_robots_check": True, "enabled": False,
        "disabled_reason": "robots.txt 503 = disallow",
    },
]

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
_PHONE = re.compile(
    r"(?:\+|00)\s?(?:971|966|974|965|968|973)[\s\-.]?\d{1,2}[\s\-.]?\d{3}[\s\-.]?\d{3,4}"
    r"|\b0(?:5\d|[1-4679])[\s\-.]?\d{3}[\s\-.]?\d{3,4}\b"
    r"|\b(?:800|9200)\d{4,6}\b"
)
_CHALLENGE = re.compile(
    r"cf-challenge|challenge-platform|cf_chl_|"
    r"<title>\s*Just a moment|g-recaptcha|h-captcha|"
    r"hcaptcha|recaptcha/api|captcha", re.I
)
_LOGIN_PATH = re.compile(r"/(log-?in|sign-?in|signin|auth|account|login)", re.I)

def normalize_email(email: str) -> str | None:
    e = (email or "").strip().strip(".,;:<>()[]\"'").lower()
    if e.startswith("mailto:"):
        e = e[7:].split("?")[0]
    if not _EMAIL.fullmatch(e):
        return None
    local, domain = e.split("@", 1)
    if local in JUNK_LOCALS or domain.rsplit(".", 1)[-1] in ASSET_TLDS:
        return None
    if any(domain == d or domain.endswith("." + d) for d in JUNK_EMAIL_DOMAINS):
        return None
    return e

_CODES = {"AE": "971", "SA": "966", "QA": "974", "KW": "965", "OM": "968", "BH": "973"}

def normalize_phone(phone: str, default_country: str) -> str | None:
    s = re.sub(r"[\s\-(\.\u200e\u200f]", "", str(phone or ""))
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

def is_role_email(email: str) -> bool:
    e = normalize_email(email)
    return bool(e) and e.split("@")[0] in ROLE_PREFIXES

def _slug(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", (text or "").lower())

def dedupe_companies(companies: list) -> list:
    out, by_key = [], {}
    for c in companies or []:
        if not isinstance(c, dict):
            continue
        email = normalize_email(c.get("email") or "")
        key = ("e", email) if email else ("n", _slug(c.get("company_name")), c.get("phone_e164") or "")
        if key in by_key:
            kept = by_key[key]
            for k, v in c.items():
                if kept.get(k) in (None, "", []) and v not in (None, "", []):
                    kept[k] = v
            continue
        c = dict(c)
        by_key[key] = c
        out.append(c)
    return out

def _sector_words(sector: str) -> list[str]:
    s = SECTORS.get(sector, {})
    words = re.findall(r"[a-z]{4,}", " ".join(s.get("en") or []).lower())
    return words + [w for w in " ".join(s.get("ar") or []).split() if len(w) >= 3]

def rank_company(company: dict) -> int:
    c = company or {}
    score = 0
    if c.get("email") and is_role_email(c["email"]): score += 10
    if c.get("phone_e164"): score += 10
    if c.get("website"): score += 20
    # تم تصحيح هذا السطر
    text = " ".join(str(c.get(k) or "") for k in ("company_name", "title", "snippet")).lower()
    if any(w in text for w in _sector_words(c.get("sector") or "")): score += 30
    if (c.get("country") or "").upper() in CITIES: score += 20
    if c.get("email"): score += 10
    return min(100, score)

def _load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {"emails": [], "names": [], "domains": [], "phones": []}
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"emails": [], "names": [], "domains": [], "phones": []}

def _save_seen(seen: dict) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    seen["updated_at"] = datetime.now(timezone.utc).isoformat()
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

def _filter_seen(companies: list, country: str = "AE") -> tuple:
    seen = _load_seen()
    seen_emails = {e.lower() for e in seen.get("emails", [])}
    seen_names = {n.lower() for n in seen.get("names", [])}
    seen_domains = {d.lower() for d in seen.get("domains", [])}
    fresh = []
    skipped = 0
    for c in companies:
        email = (c.get("email") or "").lower()
        name = (c.get("company_name") or "").lower().strip()
        website = c.get("website") or ""
        host = urlsplit(website).netloc.lower().replace("www.", "") if website else ""
        if (email and email in seen_emails) or (name and name in seen_names) or (host and host in seen_domains):
            skipped += 1
            continue
        fresh.append(c)
    for c in fresh:
        if c.get("email"): seen_emails.add(c["email"].lower())
        if c.get("company_name"): seen_names.add(c["company_name"].lower().strip())
        if c.get("website"):
            h = urlsplit(c["website"]).netloc.lower().replace("www.", "")
            if h: seen_domains.add(h)
    seen["emails"] = sorted(seen_emails)
    seen["names"] = sorted(seen_names)
    seen["domains"] = sorted(seen_domains)
    _save_seen(seen)
    return fresh, skipped

class Budget:
    def __init__(self, max_serper_calls: int = MAX_SERPER_CALLS_PER_RUN, max_pages: int = MAX_PAGES_PER_RUN):
        self.max_serper_calls = min(int(max_serper_calls), MAX_SERPER_CALLS_PER_RUN)
        self.max_pages = min(int(max_pages), MAX_PAGES_PER_RUN)
        self.serper_calls = 0
        self.pages_fetched = 0
    def can_query(self) -> bool:
        return self.serper_calls < self.max_serper_calls
    def can_fetch(self) -> bool:
        return self.pages_fetched < self.max_pages

class _Node:
    _slots_ = ("tag", "attrs", "children", "parent")
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs = tag, dict(attrs or {})
        self.children, self.parent = [], parent
    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, _Node):
                yield from c.iter()
    def text(self):
        if self.tag in ("script", "style", "noscript"):
            return ""
        return " ".join(" ".join(c.text() if isinstance(c, _Node) else c for c in self.children).split())
    def classes(self):
        return (self.attrs.get("class") or "").split()
    def find_all(self, tag):
        return [n for n in self.iter() if n.tag == tag]

_VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "embed", "source", "track", "wbr"}

class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self.cur = self.root
    def handle_starttag(self, tag, attrs):
        n = _Node(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.children.append(n)
        if tag not in _VOID:
            self.cur = n
    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, [(k, v or "") for k, v in attrs], self.cur))
    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent
    def handle_data(self, data):
        self.cur.children.append(data)

def _parse(html: str) -> _Node:
    t = _Tree()
    try:
        t.feed(html or "")
        t.close()
    except Exception:
        pass
    return t.root

def _meta(root: _Node, key: str) -> str:
    for m in root.find_all("meta"):
        if key in (m.attrs.get("property"), m.attrs.get("name")):
            return (m.attrs.get("content") or "").strip()
    return ""

def _emails_in(html: str) -> list[str]:
    root = _parse(html)
    found = [a.attrs.get("href", "") for a in root.find_all("a") if a.attrs.get("href", "").lower().startswith("mailto:")]
    found += _EMAIL.findall(html or "")
    out = []
    for e in found:
        n = normalize_email(e)
        if n and n not in out:
            out.append(n)
    return out

def _phones_in(html_or_text: str, country: str) -> list[str]:
    raw = re.findall(r'href=[\'"]tel:([^\'"]+)', html_or_text or "", re.I)
    text = re.sub(r"<[^>]+>", " ", html_or_text or "")
    raw += _PHONE.findall(text)
    out = []
    for r in raw:
        p = normalize_phone(r, country)
        if p and p not in out:
            out.append(p)
    return out

def _clean_title(title: str) -> str:
    # تم تصحيح الخطأ هنا: إزالة الرموز الخاطئة من الـ regex
    t = re.split(r"\s+[|:\-—]\s+", (title or "").strip())[0]
    return " ".join(t.split())[:120]

def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h

def _country_of_host(host: str) -> str | None:
    tld = (host or "").rsplit(".", 1)[-1]
    return {"ae": "AE", "sa": "SA", "qa": "QA", "kw": "KW", "om": "OM", "bh": "BH"}.get(tld)

def _skip_domain(host: str) -> bool:
    if not host: return True
    if any(host == d or host.endswith("." + d) for d in SKIP_DOMAINS): return True
    return bool(re.search(r"(\^|\\.)(gov|edu|ac|mil)(\.|\$)", host))

BLOCKED_DOMAINS = {
    "scribd.com", "slideshare.net", "academia.edu", "issuu.com", "calameo.com",
    "ifind.ae", "yellowpages.com", "yellowpages-uae.com",
    "yello.ae", "connect.ae", "dubailocal.ae",
    "sovereignwhale.com", "quanticdata.io",
    "crunchbase.com", "zoominfo.com", "apollo.io",
    "google.com", "google.ae", "google.sa", "bing.com", "yahoo.com",
    "duckduckgo.com", "facebook.com", "instagram.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com",
    "youtube.com", "pinterest.com", "snapchat.com",
    "wikipedia.org", "medium.com", "reddit.com", "quora.com",
    "amazon.ae", "amazon.sa", "amazon.com", "noon.com",
    "desertcart.ae", "desertcart.com",
    "booking.com", "tripadvisor.com", "airbnb.com",
    "agoda.com", "expedia.com", "hotels.com",
    "alwatan.ae", "gulfnews.com", "khaleejtimes.com",
    "thenationalnews.com", "arabianbusiness.com",
    "github.com", "gitlab.com", "vercel.app", "netlify.app", "cloudflare.com",
}

DOCUMENT_DOMAINS = {"scribd.com", "slideshare.net", "academia.edu", "issuu.com", "calameo.com"}
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
DOCUMENT_PATHS = ("/news/", "/article/", "/blog/", "/press/", "/wp-content/uploads/", "/storage/", "/documents/")
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com", "aol.com", "protonmail.com"}

TITLE_SEPARATORS = (":", "—", "|", "»", "«", "-", "...", "…")
_TITLE_WORDS_EN = re.compile(
    r"\b(guide|how to|tips|blog|news|article|about us|contact us|home page|welcome to)\b", re.I
)
TITLE_PHRASES = ("services -", "products -")
TITLE_WORDS_AR = ("رئيسي", "دليل", "مقال", "أخبار", "تقرير", "كيف", "فضل", "من نحن", "الرئيسية", "قائمة")
GENERIC_PAGE_NAMES = {"home", "homepage", "index", "contact", "about", "welcome"}

_BRAND_MARKER = re.compile(r"(?<![a-z])(fz-llc|l\.l\.c|llc|fze|dmcc|est\.|established|group|holding)", re.I)
_OFF_SECTOR = ("ai-automation", "web-design", "software", "saas", "consulting", "marketing-agency", "leads")
SECTOR_MISMATCH_WORDS = {
    "restaurants": _OFF_SECTOR + ("clinic", "dental", "real-estate", "law-firm"),
    "clinics": _OFF_SECTOR + ("restaurant", "real-estate", "law-firm"),
    "real_estate": _OFF_SECTOR + ("restaurant", "clinic", "dental", "law-firm"),
    "salons": _OFF_SECTOR + ("restaurant", "real-estate", "law-firm"),
    "lawyers": tuple(w for w in _OFF_SECTOR if w != "consulting") + ("restaurant", "clinic", "dental", "salon"),
}

REJECT_REASONS = ("title_like_name", "blocked_domain", "document_source")
CLEAN_KINDS = ("phone_wrong_country", "email_domain_mismatch", "sector_mismatch")
_SECOND_LEVEL = {"co", "com", "net", "org", "gov", "ac", "edu", "sch"}

def _base_domain(host: str) -> str:
    labels = [p for p in (host or "").lower().strip(".").split(".") if p]
    if labels[:1] == ["www"]: labels = labels[1:]
    n = 3 if (len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2) else 2
    return "." .join(labels[-n:])

def _domain_blocked(host: str, domains=None) -> bool:
    host = (host or "").lower().strip(".")
    return bool(host) and any(host == d or host.endswith("." + d) for d in (domains or BLOCKED_DOMAINS))

def _email_domain(email) -> str:
    e = (email or "").strip().lower()
    return e.split("@", 1)[1] if "@" in e else ""

def is_title_like(name) -> bool:
    n = " ".join(str(name or "").split())
    if len(n) < 3: # رفض الأسماء القصيرة جداً
        return True
    if _BRAND_MARKER.search(n):
        return False
    low = n.lower()
    
    # فلترة الكلمات الدليلية والوهمية
    junk_keywords = ["directory", "page ", "results", "search", "category", "listing", "best ", "top ", "how to"]
    if any(kw in low for kw in junk_keywords):
        return True
        
    # رفض الأسماء التي تحتوي على أرقام في النهاية (مثل Page 2)
    if re.search(r'\b\d+$', n):
        return True

    return (
        len(n) > 65
        or low.startswith(("http", "www."))
        or low in GENERIC_PAGE_NAMES
        or any(s in n for s in TITLE_SEPARATORS)
        or any(p in low for p in TITLE_PHRASES)
        or bool(_TITLE_WORDS_EN.search(n))
        or any(w in n for w in TITLE_WORDS_AR)
    )

def is_document_source(url) -> bool:
    path = (urlsplit(url or "").path or "").lower()
    if path.endswith(DOCUMENT_EXTENSIONS): return True
    if any(p in path.rstrip("/") + "/" for p in DOCUMENT_PATHS): return True
    return _domain_blocked(_host(url or ""), DOCUMENT_DOMAINS)

def screen_company(company: dict, country: str = "AE") -> tuple:
    c = dict(company or {})
    if is_title_like(c.get("company_name")):
        return None, "title_like_name", []
    if is_document_source(c.get("source_url")):
        return None, "document_source", []
    email_dom = _email_domain(c.get("email"))
    web_dom = _host(c.get("website")) or ""
    if any(_domain_blocked(h) for h in (_host(c.get("source_url") or ""), web_dom, email_dom)):
        return None, "blocked_domain", []
    notes = []
    code = _CODES.get((country or "").upper())
    phone = c.get("phone_e164")
    if phone and code and not str(phone).startswith("+" + code):
        notes.append("phone_wrong_country: %s" % phone)
        c["phone_e164"] = None
    if email_dom and (email_dom in FREE_EMAIL_DOMAINS or (web_dom and _base_domain(email_dom) != _base_domain(web_dom))):
        notes.append("email_domain_mismatch: %s vs %s" % (email_dom, web_dom or "no website"))
        c["confidence"] = "low"
    words = SECTOR_MISMATCH_WORDS.get(c.get("sector"), ())
    hay = "%s %s" % (c.get("source_url") or "", c.get("website") or "")
    if any(w in hay.lower() for w in words):
        notes.append("sector_mismatch: %s" % c["sector"])
        c["sector"] = "unknown"
    if notes: c["quality_warnings"] = notes
    return c, None, notes

def empty_filter_stats() -> dict:
    return {
        "companies_rejected": dict(dict.fromkeys(REJECT_REASONS, 0), total=0),
        "companies_cleaned": dict.fromkeys(CLEAN_KINDS, 0),
        "rejected_companies": [],
    }

def merge_filter_stats(runs) -> dict:
    out = empty_filter_stats()
    for r in runs or []:
        for k, v in (r.get("companies_rejected") or {}).items():
            out["companies_rejected"][k] = out["companies_rejected"].get(k, 0) + v
        for k, v in (r.get("companies_cleaned") or {}).items():
            out["companies_cleaned"][k] = out["companies_cleaned"].get(k, 0) + v
        out["rejected_companies"] += r.get("rejected_companies") or []
    return out

def _reject(out: dict, company: dict, reason: str) -> None:
    out["companies_rejected"][reason] += 1
    out["companies_rejected"]["total"] += 1
    out["rejected_companies"].append({
        "company_name": company.get("company_name"),
        "source_url": company.get("source_url"),
        "website": company.get("website"),
        "email": company.get("email"),
        "sector": company.get("sector"),
        "reason": reason,
    })

def http_get(url: str, timeout_s: float = PAGE_TIMEOUT_S, max_bytes: int = PAGE_MAX_BYTES) -> tuple:
    if requests is None: raise RuntimeError("requests not installed")
    deadline = time.monotonic() + timeout_s
    with requests.get(url, headers={"User-Agent": UA}, timeout=timeout_s, stream=True, allow_redirects=True) as r:
        ctype = (r.headers.get("Content-Type") or "").lower()
        if r.status_code >= 400 or (ctype and "html" not in ctype and "text" not in ctype):
            return r.status_code, None, r.url
        chunks, size = [], 0
        for chunk in r.iter_content(65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes or time.monotonic() > deadline: break
        body = b"".join(chunks)[:max_bytes]
        return r.status_code, body.decode(r.encoding or "utf-8", "replace"), r.url

def _default_serper_post(url, headers, body, timeout):
    if requests is None: raise RuntimeError("requests not installed")
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    return r.status_code, (r.json() if r.content else {})

class RobotsCache:
    def __init__(self, fetcher=None):
        self._fetch = fetcher or http_get
        self._cache = {}
    def check(self, url: str, token: str = UA_TOKEN) -> tuple:
        s = urlsplit(url)
        host = (s.hostname or "").lower()
        if host not in self._cache:
            try:
                res = tuple(self._fetch("%s://%s/robots.txt" % (s.scheme or "https", s.netloc)))
                status, text = res[0], res[1]
            except Exception:
                status, text = None, None
            if status is None or status >= 500:
                self._cache[host] = None
            else:
                rp = RobotFileParser()
                rp.parse((text or "").splitlines() if 200 <= status < 300 else [])
                self._cache[host] = rp
        rp = self._cache[host]
        if rp is None: return False, "robots_unreachable"
        return (True, "") if rp.can_fetch(token, url) else (False, "robots_disallowed")

def build_queries(sector: str, country: str = "AE") -> list:
    phrases = SECTORS.get(sector, {}).get("en", [])
    if not phrases: return []
    country = (country or "AE").upper()
    if country not in CITIES: country = "AE"
    tld = country.lower()
    pool_phrases = list(phrases)
    random.shuffle(pool_phrases)
    chosen = pool_phrases[:3]
    pool_cities = list(CITIES[country])
    random.shuffle(pool_cities)
    cities = pool_cities[:3]
    def city_term(c): return "%s" % c if " " in c else c
    email_patterns = ["info@", "contact@", "sales@", "admin@", "email.com", "hotmail.com"]
    queries = []
    for i, phrase in enumerate(chosen):
        city = cities[i % len(cities)]
        email = random.choice(email_patterns)
        queries.append(f'"{phrase}" {city_term(city)} {email}')
    random.shuffle(pool_phrases)
    p1 = pool_phrases[0]
    p2 = pool_phrases[1] if len(pool_phrases) > 1 else pool_phrases[0]
    queries.append(f'site:*.{tld} "{p1}" "info@"')
    queries.append(f'site:*.{tld} "{p2}" "contact@"')
    return queries[:QUERIES_PER_SECTOR]

def sector_phrase(sector: str) -> str:
    en = [p.strip() for p in (SECTORS[sector].get("en") or [])]
    return next((p for p in en if p), "")

def _result(sector, country, source):
    return dict(
        {"ok": False, "sector": sector, "country": country, "source": source, "serper_calls": 0, "pages_fetched": 0, "companies": [], "warnings": []},
        **empty_filter_stats(),
    )

def _city_of(text: str, country: str) -> str | None:
    all_cities = CITIES.get(country, []) + ["Al Ain", "Makkah", "Madinah", "Khobar"]
    for c in all_cities:
        if c.lower() in (text or "").lower(): return c
    return None

def find_via_serper(sector: str, country: str = "AE", max_results: int = 20, *, serper_key: str | None = None, http_post=None, sleep=time.sleep, delay_between_queries_s: float = 1.5, fetcher=None, budget: Budget | None = None, robots=None, delay_between_pages_s: float = 1.0, progress_callback=None, strict_filters: bool = True, filter_seen: bool = True) -> dict:
    out = _result(sector, country, "serper")
    out["strict_filters"] = bool(strict_filters)
    country = (country or "AE").upper()
    if sector not in SECTORS or country not in CITIES:
        out["warnings"].append("unknown sector or country")
        return out
    key = (serper_key if serper_key is not None else os.getenv("SERPER_API_KEY") or "").strip()
    if not key:
        out["warnings"].append("serper_not_configured")
        return out
    budget = budget or Budget()
    fetch = fetcher or http_get
    robots = robots or RobotsCache(fetch)
    post = http_post or _default_serper_post
    log = progress_callback or (lambda *_a, **_k: None)
    companies, seen_urls, fetched_here = [], set(), 0
    for i, q in enumerate(build_queries(sector, country)):
        if len(companies) >= max_results: break
        if not budget.can_query():
            out["warnings"].append("serper_cap_reached (%d per run)" % budget.max_serper_calls)
            break
        if i: sleep(max(0.0, float(delay_between_queries_s)))
        budget.serper_calls += 1
        out["serper_calls"] += 1
        log("serper %s/%s query %d: %s" % (sector, country, i + 1, q))
        try:
            status, data = post(SERPER_URL, {"X-API-KEY": key, "Content-Type": "application/json"}, {"q": q, "gl": country.lower(), "num": 10}, 15)
        except Exception as e:
            out["warnings"].append("serper_failed:%s" % type(e).__name__)
            continue
        if not 200 <= int(status) < 300:
            out["warnings"].append("serper_http_%s" % status)
            continue
        for item in (data or {}).get("organic", []):
            if len(companies) >= max_results: break
            url = (item.get("link") or "").strip()
            host = _host(url)
            if not url.startswith(("http://", "https://")) or url in seen_urls: continue
            seen_urls.add(url)
            if _skip_domain(host): continue
            title = item.get("title") or ""
            snippet = item.get("snippet") or ""
            emails = _emails_in(title + " " + snippet)
            phones = _phones_in(snippet, country)
            name = _clean_title(title)
            website = "https://%s" % host
            from_page = False
            prelim = {"company_name": name, "source_url": url, "website": website, "sector": sector}
            if not emails and strict_filters and (is_document_source(url) or _domain_blocked(host)):
                _reject(out, prelim, screen_company(prelim, country)[1])
                continue
            if not emails:
                if not budget.can_fetch():
                    out["warnings"].append("page_cap_reached (%d per run)" % budget.max_pages)
                    continue
                ok, why = robots.check(url)
                if not ok:
                    out["warnings"].append("%s: %s" % (why, host))
                    continue
                if fetched_here: sleep(max(0.0, float(delay_between_pages_s)))
                budget.pages_fetched += 1
                out["pages_fetched"] += 1
                fetched_here += 1
                try:
                    res = tuple(fetch(url))
                except Exception:
                    out["warnings"].append("fetch_failed:%s" % host)
                    continue
                status, html = res[0], res[1]
                if status != 200 or not html: continue
                emails = _emails_in(html)
                if len({e.split("@")[1] for e in emails}) > 3:
                    out["warnings"].append("list_page_skipped: %s" % host)
                    continue
                root = _parse(html)
                name = (_meta(root, "og:site_name") or _clean_title(" ".join(t.text() for t in root.find_all("title"))) or name)
                canon = next((l.attrs.get("href") for l in root.find_all("link") if "canonical" in (l.attrs.get("rel") or "").lower()), "") or _meta(root, "og:url")
                if canon and canon.startswith("http") and not _skip_domain(_host(canon)): website = "https://%s" % _host(canon)
                phones = phones or _phones_in(html, country)
                from_page = True
            if not emails and not phones: continue
            email = emails[0] if emails else None
            if email and _host("https://" + email.split("@")[1]) == _host(website): confidence = "high"
            elif email: confidence = "medium"
            else: confidence = "low"
            cand = {
                "company_name": name or host,
                "email": email,
                "phone_e164": phones[0] if phones else None,
                "website": website,
                "sector": sector,
                "country": _country_of_host(_host(website)) or country,
                "city": _city_of(title + " " + snippet, _country_of_host(_host(website)) or country),
                "source": "serper",
                "source_url": url,
                "confidence": confidence,
                "email_found_on": "page" if from_page else "snippet",
            }
            if strict_filters:
                kept, reason, notes = screen_company(cand, country)
                if kept is None:
                    _reject(out, cand, reason)
                    continue
                for n in notes:
                    out["companies_cleaned"][n.split(":", 1)[0]] += 1
                    out["warnings"].append(n)
                cand = kept
            companies.append(cand)
    for reason in REJECT_REASONS:
        if out["companies_rejected"][reason]:
            out["warnings"].append("rejected:%s: %d" % (reason, out["companies_rejected"][reason]))
    companies = dedupe_companies(companies)
    if filter_seen and companies:
        companies, skipped_seen = _filter_seen(companies, country)
        if skipped_seen:
            out["warnings"].append("seen_skipped: %d" % skipped_seen)
            out["seen_skipped"] = skipped_seen
        else:
            out["seen_skipped"] = 0
    for c in companies:
        c["rank"] = rank_company(c)
    companies.sort(key=lambda c: -c["rank"])
    out["companies"] = companies[:max_results]
    out["ok"] = True
    return out

class _PWPage:
    def __init__(self, page): self._p = page
    def goto(self, url, timeout_ms=30000):
        resp = self._p.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        return resp.status if resp else None
    def content(self): return self._p.content()
    @property
    def url(self): return self._p.url

@contextlib.contextmanager
def _real_page(headless: bool = True):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try: yield _PWPage(browser.new_context().new_page())
        finally: browser.close()

def _directory_urls(src: dict, sector: str, country: str) -> list:
    slug = src.get("slugs", {}).get(sector)
    if not slug: return []
    urls = []
    for city in CITIES[country]:
        city_slug = city.lower().replace(" ", "-")
        urls.append(src["base"] + src["search_path"].format(slug=slug, city=city_slug, query=quote(SECTORS[sector]["en"][0])))
    first = (urls[0] + src.get("page_suffix", "").format(page=2) if src.get("page_suffix") else None)
    return (urls + ([first] if first else []))[:MAX_DIRECTORY_PAGES]

def _cards(html: str, src: dict, sector: str, country: str, page_url: str) -> list:
    root = _parse(html)
    want = src.get("card_class", "company")
    out = []
    for n in root.iter():
        if n.tag not in ("div", "article", "li") or want not in n.classes(): continue
        heads = [h for t in ("h3", "h2", "h4") for h in n.find_all(t)]
        name = heads[0].text() if heads else ""
        if not name: continue
        address = next((d.text() for d in n.iter() if "address" in d.classes()), "")
        card_html = "".join(_render(n))
        emails = _emails_in(card_html)
        phones = _phones_in(n.text(), country)
        website = None
        for a in n.find_all("a"):
            href = a.attrs.get("href", "")
            if href.startswith("http") and _host(href) != _host(page_url) and not _skip_domain(_host(href)):
                website = "https://%s" % _host(href)
                break
        out.append({
            "company_name": name[:120], "email": emails[0] if emails else None, "phone_e164": phones[0] if phones else None,
            "website": website, "sector": sector, "country": country, "city": _city_of(address or n.text(), country),
            "source": "playwright", "source_url": page_url, "confidence": "high" if emails else ("medium" if phones else "low"),
            "directory": src["name"],
        })
    return out

def _render(n: _Node):
    yield "<%s %s>" % (n.tag, " ".join('%s="%s"' % kv for kv in n.attrs.items()))
    for c in n.children:
        if isinstance(c, _Node): yield from _render(c)
        else: yield c
    yield "</%s>" % n.tag

class _TimeUp(Exception): pass

def _wall(html: str, url: str) -> str | None:
    if _LOGIN_PATH.search(urlsplit(url or "").path or ""): return "login_wall"
    if re.search(r'<input[^>]+type=["\']?password', html or "", re.I): return "login_wall"
    if _CHALLENGE.search(html or ""): return "captcha_or_challenge"
    return None

def find_via_playwright(sector: str, country: str = "AE", max_results: int = 60, *, headless: bool = True, delay_between_pages_s: float = 3.0, respect_robots: bool = True, max_minutes: int = 10, page_factory=None, robots_fetcher=None, sleep=time.sleep, clock=time.monotonic, progress_callback=None) -> dict:
    out = _result(sector, country, "playwright")
    country = (country or "AE").upper()
    log = progress_callback or (lambda *_a, **_k: None)
    if sector not in SECTORS or country not in CITIES:
        out["warnings"].append("unknown sector or country")
        return out
    if not respect_robots: out["warnings"].append("respect_robots=False ignored")
    sources = [s for s in DIRECTORY_SOURCES if s["country"] == country]
    for s in sources:
        if not s.get("enabled"): out["warnings"].append("%s skipped: %s" % (s["name"], s.get("disabled_reason")))
    sources = [s for s in sources if s.get("enabled")]
    if not sources:
        out["warnings"].append("no enabled directory for %s" % country)
        out["ok"] = True
        return out
    robots = RobotsCache(robots_fetcher)
    deadline = clock() + max(0.0, float(max_minutes)) * 60
    factory = page_factory or (lambda: _real_page(headless))
    companies, loaded = [], 0
    try:
        with factory() as page:
            for src in sources:
                for url in _directory_urls(src, sector, country):
                    if len(companies) >= max_results: break
                    if clock() >= deadline:
                        out["warnings"].append("time_limit_reached")
                        raise _TimeUp
                    ok, why = robots.check(url, "*")
                    if not ok:
                        out["warnings"].append("%s skipped: %s (%s)" % (src["name"], why, urlsplit(url).path))
                        break
                    if loaded: sleep(max(0.0, float(delay_between_pages_s)))
                    loaded += 1
                    out["pages_fetched"] += 1
                    log("playwright %s: %s" % (src["name"], url))
                    try:
                        status = page.goto(url)
                        html, final = page.content(), page.url
                    except Exception as e:
                        out["warnings"].append("%s page failed: %s" % (src["name"], type(e).__name__))
                        break
                    wall = _wall(html, final)
                    if wall:
                        out["warnings"].append("%s skipped: %s" % (src["name"], wall))
                        break
                    if status and status >= 400:
                        out["warnings"].append("%s HTTP %s" % (src["name"], status))
                        break
                    companies += _cards(html, src, sector, country, final)
    except _TimeUp: pass
    except ImportError: out["warnings"].append("playwright_not_installed")
    except Exception as e:
        msg = str(e)
        if "Executable doesn't exist" in msg or "playwright install" in msg: out["warnings"].append("playwright_browser_missing")
        else: out["warnings"].append("playwright_failed:%s" % type(e).__name__)
    companies = dedupe_companies(companies)
    for c in companies: c["rank"] = rank_company(c)
    companies.sort(key=lambda c: -c["rank"])
    out["companies"] = companies[:max_results]
    out["ok"] = True
    return out

def plan(sectors, country: str = "AE", mode: str = "serper") -> dict:
    if isinstance(sectors, str): sectors = [sectors]
    country = country.upper()
    steps = []
    for s in sectors:
        if mode == "serper": steps.append({"sector": s, "queries": build_queries(s, country)})
        else:
            per = []
            for src in DIRECTORY_SOURCES:
                if src["country"] != country: continue
                per.append({
                    "directory": src["name"], "enabled": bool(src.get("enabled")), "reason": src.get("disabled_reason"),
                    "urls": (_directory_urls(src, s, country) if src.get("enabled") else []),
                })
            steps.append({"sector": s, "directories": per})
    calls = min(sum(len(st.get("queries", [])) for st in steps), MAX_SERPER_CALLS_PER_RUN)
    return {
        "mode": mode, "country": country, "sectors": list(sectors),
        "queries": [q for st in steps for q in st.get("queries", [])],
        "serper_calls_planned": calls if mode == "serper" else 0,
        "page_fetch_cap": (MAX_PAGES_PER_RUN if mode == "serper" else MAX_DIRECTORY_PAGES * len(sectors)),
        "steps": steps,
    }

def default_out_path(sector: str, country: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUT_DIR / ("finder_%s_%s_%s.json" % (sector, country, ts))

def _write(path, data) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
    return str(p)

def find_prospects(sector: str, country: str = "AE", max_results: int = 20, mode: str = "serper", *, out_path: str | None = None, progress_callback=None, strict_filters: bool = True, filter_seen: bool = True, **kwargs) -> dict:
    t0 = time.perf_counter()
    if mode == "playwright":
        r = find_via_playwright(sector, country, max_results, progress_callback=progress_callback, **kwargs)
    else:
        r = find_via_serper(sector, country, max_results, progress_callback=progress_callback, strict_filters=strict_filters, filter_seen=filter_seen, **kwargs)
    comps = r["companies"]
    stats = merge_filter_stats([r])
    out = {
        "ok": r["ok"], "mode": mode, "sector": sector, "country": (country or "").upper(),
        "companies_found": len(comps), "companies_with_email": sum(1 for c in comps if c.get("email")),
        "companies_with_phone": sum(1 for c in comps if c.get("phone_e164")),
        "serper_calls": r.get("serper_calls", 0), "pages_fetched": r.get("pages_fetched", 0),
        "duration_ms": int((time.perf_counter() - t0) * 1000), "strict_filters": bool(r.get("strict_filters", False)),
        "seen_skipped": r.get("seen_skipped", 0), **stats, "out_path": None, "companies": comps, "warnings": r["warnings"],
    }
    if out_path: out["out_path"] = _write(out_path, out)
    return out

def find_all_sectors(sectors: list, country: str = "AE", max_results: int = 20, mode: str = "serper", *, out_path: str | None = None, progress_callback=None, filter_seen: bool = True, **kwargs) -> dict:
    budget = kwargs.pop("budget", None) or Budget()
    t0 = time.perf_counter()
    runs, merged, warnings, full = [], [], [], []
    for s in sectors:
        extra = dict(kwargs)
        if mode == "serper": extra["budget"] = budget
        r = find_prospects(s, country, max_results, mode, progress_callback=progress_callback, filter_seen=filter_seen, **extra)
        full.append(r)
        runs.append({k: r[k] for k in ("sector", "companies_found", "companies_with_email", "serper_calls", "pages_fetched", "companies_rejected", "companies_cleaned")})
        merged += r["companies"]
        warnings += ["%s: %s" % (s, w) for w in r["warnings"]]
    merged = dedupe_companies(merged)
    stats = merge_filter_stats(full)
    out = {
        "ok": True, "mode": mode, "sector": "all", "country": country.upper(), "sectors": runs,
        "companies_found": len(merged), "companies_with_email": sum(1 for c in merged if c.get("email")),
        "companies_with_phone": sum(1 for c in merged if c.get("phone_e164")),
        "serper_calls": sum(r["serper_calls"] for r in runs), "pages_fetched": sum(r["pages_fetched"] for r in runs),
        "duration_ms": int((time.perf_counter() - t0) * 1000), "strict_filters": any(r["strict_filters"] for r in full),
        "seen_skipped": sum(r.get("seen_skipped", 0) for r in full), **stats, "out_path": None, "companies": merged, "warnings": warnings,
    }
    if out_path: out["out_path"] = _write(out_path, out)
    return out

def serper_balance(serper_key: str | None = None, http_get_json=None) -> dict:
    key = (serper_key or os.getenv("SERPER_API_KEY") or "").strip()
    if not key: return {"ok": False, "reason": "serper_not_configured"}
    try:
        if http_get_json: status, data = http_get_json(SERPER_ACCOUNT_URL, {"X-API-KEY": key})
        else:
            r = requests.get(SERPER_ACCOUNT_URL, headers={"X-API-KEY": key}, timeout=10)
            status, data = r.status_code, (r.json() if r.content else {})
    except Exception as e: return {"ok": False, "reason": "request_failed:%s" % type(e).__name__}
    if status != 200 or not isinstance(data, dict): return {"ok": False, "reason": "http_%s" % status}
    return {"ok": True, "balance": data.get("balance"), "raw_keys": sorted(data)}

def _company_keys(c: dict) -> set:
    keys = set()
    e = normalize_email((c or {}).get("email") or "")
    if e: keys.add(("e", e))
    h = _host((c or {}).get("website") or "")
    if h: keys.add(("w", h))
    p = (c or {}).get("phone_e164")
    if p: keys.add(("p", p))
    return keys

def find_prospects_auto(*, sectors: list | None = None, country: str = "AE", max_per_sector: int = 20, out_dir: str | None = None, now=None, finder=None) -> dict:
    t0 = time.perf_counter()
    sectors = [s for s in (sectors or list(SECTORS)) if s in SECTORS]
    out = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    if not out.is_absolute(): out = ROOT / out
    dubai = timezone(timedelta(hours=4))
    stamp = (now or datetime.now(timezone.utc)).astimezone(dubai)
    path = out / ("daily_%s.json" % stamp.strftime("%Y%m%d"))
    run = (finder or find_all_sectors)(sectors, country, int(max_per_sector), "serper")
    seen, today = set(), []
    if out.is_dir():
        for f in sorted(out.glob("daily_*.json")):
            try: rows = json.loads(f.read_bytes().decode("utf-8")).get("companies") or []
            except (OSError, ValueError, AttributeError): continue
            for c in rows:
                if isinstance(c, dict): seen |= _company_keys(c)
                if f == path: today.append(c)
    new, dups = [], 0
    for c in run.get("companies") or []:
        k = _company_keys(c)
        if not k or k & seen:
            dups += 1
            continue
        seen |= k
        new.append(c)
    _write(path, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country": country.upper(), "sectors": sectors,
        "total_found": len(run.get("companies") or []), "new": len(new), "duplicates": dups,
        "companies": today + new, "serper_calls": run.get("serper_calls", 0),
        "companies_rejected": run.get("companies_rejected"), "warnings": (run.get("warnings") or [])[:100],
    })
    return {
        "ok": bool(run.get("ok", True)), "total_found": len(run.get("companies") or []),
        "new": len(new), "duplicates": dups, "out_path": str(path),
        "duration_ms": int((time.perf_counter() - t0) * 1000), "companies": new,
        "serper_calls": run.get("serper_calls", 0), "warnings": run.get("warnings") or [],
    }

def _print(text: str) -> None:
    try: sys.stdout.write(text)
    except UnicodeEncodeError: sys.stdout.buffer.write(text.encode("utf-8"))

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m atlas_services.prospect_finder")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sector", choices=list(SECTORS))
    g.add_argument("--all-sectors", action="store_true")
    ap.add_argument("--country", default="AE", choices=list(CITIES.keys()))
    ap.add_argument("--mode", default="serper", choices=["serper", "playwright"])
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-seen", action="store_true")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args(argv)
    sectors = list(SECTORS) if a.all_sectors else [a.sector]
    if a.dry_run:
        _print(json.dumps(plan(sectors, a.country, a.mode), ensure_ascii=False, indent=1) + "\n")
        _print("DRY RUN: nothing fetched, no Serper call made.\n")
        return 0
    out = a.out or str(default_out_path("all" if a.all_sectors else a.sector, a.country))
    log = lambda m: _print(" %s\n" % m)
    extra = {"headless": not a.headed} if a.mode == "playwright" else {}
    filter_seen = not a.no_seen
    if a.all_sectors:
        r = find_all_sectors(sectors, a.country, a.max, a.mode, out_path=out, progress_callback=log, filter_seen=filter_seen, **extra)
    else:
        r = find_prospects(a.sector, a.country, a.max, a.mode, out_path=out, progress_callback=log, filter_seen=filter_seen, **extra)
    _print(
        "PROSPECT FINDER (%s, %s)\n"
        "found ......... %s\n"
        "with email .... %s\n"
        "with phone .... %s\n"
        "seen skipped .. %s\n"
        "serper calls .. %s\n"
        "pages fetched . %s\n"
        "rejected ...... %s\n"
        "output ........ %s\n"
        % (r["mode"], r["country"], r["companies_found"], r["companies_with_email"], r["companies_with_phone"], r.get("seen_skipped", 0), r["serper_calls"], r["pages_fetched"], r["companies_rejected"]["total"], r["out_path"])
    )
    for w in r["warnings"][:20]:
        _print("warning: %s\n" % w)
    return 0 if r["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())