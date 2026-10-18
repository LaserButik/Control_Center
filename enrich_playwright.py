"""Enrich Playwright results: find websites via Serper -> extract emails.

Usage:
    .\\venv\\Scripts\\python.exe enrich_playwright.py 30
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

CC = Path(__file__).resolve().parent
PROSPECTS = CC / "data" / "prospects"

SERPER_URL = "https://google.serper.dev/search"
UA = "Mozilla/5.0 (compatible; AIMentorsBot/1.0; +https://salehhaidar.com/bot)"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
JUNK_EMAIL = (
    "noreply", "no-reply", "donotreply", "postmaster", "abuse",
    "mailer-daemon", "sentry.io", "wixpress.com", "example.com",
)
NON_CORPORATE = (
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com",
    "x.com", "tiktok.com", "youtube.com", "wikipedia.org",
    "yellowpages", "yelp.com", "tripadvisor.com", "crunchbase.com",
    "google.com", "google.ae",
)


def get_serper_key() -> str:
    """Read from env or .env file."""
    key = os.getenv("SERPER_API_KEY", "").strip()
    if key:
        return key
    env_file = CC / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("SERPER_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def find_website(company_name: str, country: str = "AE") -> str | None:
    """Use Serper to find the official website."""
    key = get_serper_key()
    if not key:
        return None

    query = f'"{company_name}" {country} official site'
    try:
        r = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "gl": country.lower(), "num": 5},
            timeout=15,
        )
    except Exception:
        return None

    if r.status_code != 200:
        return None

    data = r.json()
    for item in data.get("organic", []):
        link = item.get("link", "")
        if not link.startswith("http"):
            continue
        host = urlparse(link).netloc.lower().replace("www.", "")
        # skip non-corporate domains
        if any(d in host for d in NON_CORPORATE):
            continue
        return link
    return None


def fetch_emails(url: str, timeout: int = 10) -> list[str]:
    """Fetch a page and extract emails."""
    try:
        r = requests.get(url, headers={"User-Agent": UA},
                         timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return []
    except Exception:
        return []

    html = r.text[:500_000]
    raw = _EMAIL.findall(html)
    out = []
    for e in raw:
        e = e.lower()
        if any(j in e for j in JUNK_EMAIL):
            continue
        if e not in out:
            out.append(e)
    return out


def find_contact_pages(base_url: str) -> list[str]:
    """Try common contact page paths."""
    paths = [
        "/contact", "/contact-us", "/contactus",
        "/about", "/about-us", "/team",
    ]
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [base + p for p in paths]


def enrich_one(company: dict) -> dict:
    """Find website + emails for one company."""
    name = company.get("company_name", "")
    country = company.get("country", "AE")

    # 1. find website
    website = find_website(name, country)
    if not website:
        company["enrichment_status"] = "no_website"
        return company

    company["website"] = website
    print(f"  🔍 {website}")

    # 2. extract emails from homepage
    emails = fetch_emails(website)

    # 3. if none, try contact pages
    if not emails:
        for page in find_contact_pages(website):
            time.sleep(1)
            page_emails = fetch_emails(page)
            if page_emails:
                emails = page_emails
                break

    if emails:
        company["email"] = emails[0]
        company["emails_all"] = emails
        company["enrichment_status"] = "ok"
        print(f"  ✅ {emails[0]}")
    else:
        company["enrichment_status"] = "no_email_found"
        print(f"  ⚠️  no email")

    return company


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    # find suitable source file
    source = None
    for f in sorted(PROSPECTS.glob("finder_*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        data = json.loads(f.read_text(encoding="utf-8"))
        comps = data.get("companies", [])
        if len(comps) > 50 and sum(1 for c in comps if c.get("email")) == 0:
            source = f
            break

    if not source:
        print("❌ No suitable file found.")
        sys.exit(1)

    print(f"📂 Source: {source.name}")
    data = json.loads(source.read_text(encoding="utf-8"))
    companies = data.get("companies", [])

    # only process those without email
    to_process = [c for c in companies if not c.get("email")][:limit]
    print(f"🎯 Processing {len(to_process)} companies "
          f"(Serper credits: ~{len(to_process)})\n")

    found = 0
    for i, c in enumerate(to_process, 1):
        name = c.get("company_name", "?")
        print(f"[{i}/{len(to_process)}] {name}")
        try:
            enrich_one(c)
            if c.get("email"):
                found += 1
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {e}")
        time.sleep(1.5)

    data["companies"] = companies
    out = PROSPECTS / "playwright_enriched.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    total_with_email = sum(1 for c in companies if c.get("email"))
    print(f"\n{'='*60}")
    print(f"✅ Enriched this run: {found}/{len(to_process)}")
    print(f"📧 Total with email:  {total_with_email}")
    print(f"💾 {out}")


if __name__ == "__main__":
    main()