"""
Daily auto outreach — from discovery to sending, in one command.
UPDATED: Uses Indoctrination Engine. Fixed encoding for Windows Task Scheduler.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

# Force UTF-8 encoding for stdout to prevent cp1252 errors in Task Scheduler
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CC = Path(__file__).resolve().parent
PY = CC / "venv" / "Scripts" / "python.exe"
PROSPECTS = CC / "data" / "prospects"
EMAIL_DIR = CC / "data" / "email"
REPORTS = CC / "data" / "reports"
LOGS = CC / "data" / "scheduler"

for d in (PROSPECTS, EMAIL_DIR, REPORTS, LOGS):
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CC))

from atlas_services import indoctrination_engine as indo_engine

DUBAI_TZ = timezone(timedelta(hours=4))
START = datetime.now(DUBAI_TZ)
RUN_ID = START.strftime("%Y%m%d_%H%M%S")
SERPER_URL = "https://google.serper.dev/search"
UA = "Mozilla/5.0 (compatible; AIMentorsBot/1.0; +https://salehhaidar.com/bot)"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
JUNK_EMAILS = {
    "you@email.com", "example@email.com", "johndoe@domain.com",
    "user@example.com", "test@test.com", "name@example.com",
    "your@email.com", "email@example.com",
}
JUNK_DOMAINS = (
    "example.com", "example.org", "domain.com", "email.com",
    "yourdomain.com", "test.com",
)
ASSET_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js")
NON_CORPORATE = (
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com",
    "x.com", "tiktok.com", "youtube.com", "wikipedia.org",
    "yellowpages", "yelp.com", "tripadvisor.com", "crunchbase.com",
    "google.com", "google.ae",
    "dubailand.gov.ae", "healthfinder.ae", "startupsuae.com",
    "okadoc.com", "citysearch.ae", "propertyfinder.ae", "waze.com",
)


def log(msg: str) -> None:
    ts = datetime.now(DUBAI_TZ).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    # 1. Try printing to console (only if console exists)
    try:
        if sys.stdout is not None:
            print(line)
    except Exception:
        pass  # Ignore any print errors completely
    
    # 2. Always write to the log file
    try:
        with (LOGS / "daily_auto.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def serper_key() -> str:
    k = os.getenv("SERPER_API_KEY", "").strip()
    if k:
        return k
    f = CC / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("SERPER_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


# ══════════════════════════════════════════════════════════════════
# Preflight
# ══════════════════════════════════════════════════════════════════
def preflight() -> dict:
    log("=" * 60)
    log("PREFLIGHT")
    log("=" * 60)
    status = {"ok": True, "warnings": []}

    try:
        import config
        env = config.env_status()
        critical = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD",
                    "SMTP_FROM", "SERPER_API_KEY"]
        missing = [k for k in critical if not env.get(k)]
        if missing:
            status["ok"] = False
            status["warnings"].append(f"missing env: {missing}")
            log(f"[X] Missing env: {missing}")
        else:
            log("[OK] Environment OK")
    except Exception as e:
        status["ok"] = False
        log(f"[X] config: {e}")

    # daily sent count
    sent_log = EMAIL_DIR / "sent_log.jsonl"
    today = START.strftime("%Y-%m-%d")
    today_sent = 0
    if sent_log.exists():
        for line in sent_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                if e.get("status") == "sent" and \
                   (e.get("sent_at") or "").startswith(today):
                    today_sent += 1
            except Exception:
                pass
    status["today_sent"] = today_sent
    status["remaining"] = max(0, 25 - today_sent)
    log(f"Today: {today_sent} · Remaining: {status['remaining']}")

    # serper balance
    k = serper_key()
    if k:
        try:
            r = requests.get("https://google.serper.dev/account",
                             headers={"X-API-KEY": k}, timeout=10)
            if r.status_code == 200:
                b = r.json().get("balance")
                status["serper_balance"] = b
                log(f"Serper balance: {b}")
        except Exception:
            pass
    return status


# ══════════════════════════════════════════════════════════════════
# Step 1: Serper
# ══════════════════════════════════════════════════════════════════
def step_find_serper() -> dict:
    log("")
    log("=" * 60)
    log("STEP 1: Serper Finder")
    log("=" * 60)
    from atlas_services import prospect_finder as pf

    out = PROSPECTS / f"finder_serper_{RUN_ID}.json"
    try:
        r = pf.find_all_sectors(
            list(pf.SECTORS.keys()), "AE", 20, "serper",
            out_path=str(out), filter_seen=True,
        )
        log(f"[OK] Serper: {r['companies_with_email']} emails · "
            f"{r['companies_found']} total · "
            f"seen skipped: {r.get('seen_skipped', 0)}")
        return {"ok": True, "out": out,
                "count": r["companies_with_email"]}
    except Exception as e:
        log(f"[X] Serper: {e}")
        return {"ok": False, "out": None, "count": 0}


# ══════════════════════════════════════════════════════════════════
# Step 2: Playwright
# ══════════════════════════════════════════════════════════════════
def step_find_playwright() -> dict:
    log("")
    log("=" * 60)
    log("STEP 2: Playwright Finder")
    log("=" * 60)
    from atlas_services import prospect_finder as pf

    out = PROSPECTS / f"finder_playwright_{RUN_ID}.json"
    try:
        r = pf.find_all_sectors(
            list(pf.SECTORS.keys()), "AE", 60, "playwright",
            out_path=str(out), filter_seen=False,
        )
        log(f"[OK] Playwright: {r['companies_found']} companies")
        return {"ok": True, "out": out, "count": r["companies_found"]}
    except Exception as e:
        log(f"[!] Playwright: {e}")
        return {"ok": False, "out": None, "count": 0}


# ══════════════════════════════════════════════════════════════════
# Step 3: Enrich
# ══════════════════════════════════════════════════════════════════
def _find_website(name: str) -> str | None:
    k = serper_key()
    if not k:
        return None
    try:
        r = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": k, "Content-Type": "application/json"},
            json={"q": f'"{name}" AE official site',
                  "gl": "ae", "num": 5},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        for item in r.json().get("organic", []):
            link = item.get("link", "")
            if not link.startswith("http"):
                continue
            host = urlparse(link).netloc.lower().replace("www.", "")
            if any(d in host for d in NON_CORPORATE):
                continue
            return link
    except Exception:
        return None
    return None


def _fetch_emails(url: str) -> list[str]:
    try:
        r = requests.get(url, headers={"User-Agent": UA},
                         timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return []
    except Exception:
        return []
    html = r.text[:500_000]
    out = []
    for e in _EMAIL.findall(html):
        e = e.lower()
        if any(j in e for j in JUNK_EMAILS):
            continue
        if e.endswith(ASSET_ENDINGS):
            continue
        if re.search(r"[a-f0-9]{20,}", e):
            continue
        if e not in out:
            out.append(e)
    return out


def step_enrich(source: Path, limit: int = 30) -> dict:
    log("")
    log("=" * 60)
    log(f"STEP 3: Enrich up to {limit}")
    log("=" * 60)

    if not source or not source.exists():
        log("[!] no source")
        return {"ok": False, "count": 0}

    data = json.loads(source.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    no_email = [c for c in companies if not c.get("email")][:limit]

    if not no_email:
        log("[i] All companies have emails")
        return {"ok": True, "count": 0, "file": source}

    log(f"Processing {len(no_email)} companies")
    enriched = 0
    for i, c in enumerate(no_email, 1):
        name = c.get("company_name", "?")
        log(f"  [{i}/{len(no_email)}] {name[:40]}")
        website = _find_website(name)
        if not website:
            continue
        c["website"] = website
        emails = _fetch_emails(website)
        if not emails:
            for path in ("/contact", "/contact-us", "/about"):
                emails = _fetch_emails(website.rstrip("/") + path)
                if emails:
                    break
        if emails:
            c["email"] = emails[0]
            c["emails_all"] = emails
            enriched += 1
            log(f"    [OK] {emails[0]}")
        time.sleep(1.5)

    data["companies"] = companies
    out = PROSPECTS / f"enriched_{RUN_ID}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    log(f"[OK] Enriched: {enriched}/{len(no_email)}")
    return {"ok": True, "count": enriched, "file": out}


# ══════════════════════════════════════════════════════════════════
# Step 4: Clean
# ══════════════════════════════════════════════════════════════════
def step_clean(source: Path) -> dict:
    log("")
    log("=" * 60)
    log("STEP 4: Clean junk")
    log("=" * 60)

    if not source or not source.exists():
        return {"ok": False, "count": 0, "file": None}

    data = json.loads(source.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    good = []
    removed = 0

    for c in companies:
        email = (c.get("email") or "").strip().lower()
        if not email:
            continue
        if email in JUNK_EMAILS:
            removed += 1
            c["email"] = None
            continue
        domain = email.split("@")[-1]
        if domain in JUNK_DOMAINS:
            removed += 1
            c["email"] = None
            continue
        local = email.split("@")[0]
        if local in ("you", "example", "name", "user", "your"):
            removed += 1
            c["email"] = None
            continue
        if email.endswith(ASSET_ENDINGS):
            removed += 1
            c["email"] = None
            continue
        good.append(c)

    data["companies"] = good
    out = PROSPECTS / f"cleaned_{RUN_ID}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    log(f"[OK] Clean: {len(good)} valid · {removed} junk removed")
    return {"ok": True, "count": len(good), "file": out}


# ══════════════════════════════════════════════════════════════════
# Step 5: Filter
# ══════════════════════════════════════════════════════════════════
def step_filter(source: Path) -> dict:
    log("")
    log("=" * 60)
    log("STEP 5: Filter (sent + seen)")
    log("=" * 60)

    if not source or not source.exists():
        return {"ok": False, "count": 0, "file": None}

    # load sent
    sent = set()
    log_file = EMAIL_DIR / "sent_log.jsonl"
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                em = (e.get("email") or "").strip().lower()
                if em and e.get("status") in ("sent", "dry_run"):
                    sent.add(em)
            except Exception:
                pass

    state_file = EMAIL_DIR / "prospect_state.json"
    if state_file.exists():
        try:
            for k in json.loads(state_file.read_text(encoding="utf-8")).keys():
                sent.add(k.strip().lower())
        except Exception:
            pass

    data = json.loads(source.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    ready, skipped = [], 0
    for c in companies:
        email = (c.get("email") or "").strip().lower()
        sector = (c.get("sector") or "").lower()
        if not email:
            continue
        if sector == "unknown":
            continue
        if email in sent:
            skipped += 1
            continue
        ready.append(c)

    data["companies"] = ready
    out = PROSPECTS / "ready_to_send.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    log(f"[OK] Filter: {len(ready)} ready · {skipped} skipped (already sent)")
    return {"ok": True, "count": len(ready), "file": out}


# ══════════════════════════════════════════════════════════════════
# Step 6: Start Indoctrination Sequence
# ══════════════════════════════════════════════════════════════════
def step_start_indoctrination(source: Path, limit: int, dry: bool = False) -> dict:
    log("")
    log("=" * 60)
    log(f"STEP 6: Start Indoctrination ({'DRY' if dry else 'REAL'})")
    log("=" * 60)

    if not source or not source.exists():
        log("[!] no file")
        return {"started": 0, "skipped": 0, "failed": 0}

    data = json.loads(source.read_text(encoding="utf-8"))
    companies = data.get("companies", [])[:limit]

    if not companies:
        log("[i] no companies")
        return {"started": 0, "skipped": 0, "failed": 0}

    started = skipped = failed = 0
    for i, c in enumerate(companies, 1):
        email = c.get("email")
        if not email:
            continue
        # Try to guess language based on sector or company name
        lang = "en"
        if any(u'\u0600' <= char <= u'\u06FF' for char in c.get("company_name", "")):
            lang = "ar"

        res = indo_engine.start_sequence(c, language=lang, dry_run=dry, confirmed=not dry)
        status = res.get("status", res.get("reason"))
        
        if res.get("ok"):
            started += 1
            log(f"  [{i}] {c.get('company_name', '?')[:35]:35} -> started ({lang})")
        elif res.get("reason") == "already_in_sequence":
            skipped += 1
            log(f"  [{i}] {c.get('company_name', '?')[:35]:35} -> already in sequence")
        else:
            failed += 1
            log(f"  [{i}] {c.get('company_name', '?')[:35]:35} -> failed: {status}")

    log(f"[OK] Indoctrination Started: {started} · Skipped: {skipped} · Failed: {failed}")
    return {"started": started, "skipped": skipped, "failed": failed}


# ══════════════════════════════════════════════════════════════════
# Step 7: Process Due Indoctrination Emails
# ══════════════════════════════════════════════════════════════════
def step_process_due_indoctrination(dry: bool = False) -> dict:
    log("")
    log("=" * 60)
    log("STEP 7: Process Due Indoctrination Emails")
    log("=" * 60)
    try:
        res = indo_engine.process_due(dry_run=dry, confirmed=not dry)
        log(f"[OK] Processed: Sent: {res['sent']} · Blocked: {res['blocked']} · Failed: {res['failed']}")
        return res
    except Exception as e:
        log(f"[!] Process Due failed: {e}")
        return {"sent": 0, "blocked": 0, "failed": 0, "error": str(e)}


# ══════════════════════════════════════════════════════════════════
# Step 8: Report
# ══════════════════════════════════════════════════════════════════
def step_report(metrics: dict) -> None:
    log("")
    log("=" * 60)
    log("STEP 8: Report")
    log("=" * 60)

    report = {
        "date": START.strftime("%Y-%m-%d"),
        "run_id": RUN_ID,
        "duration_s": int((datetime.now(DUBAI_TZ) - START).total_seconds()),
        "metrics": metrics,
    }
    rf = REPORTS / f"daily_{START.strftime('%Y%m%d')}.json"
    rf.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    log(f"[OK] {rf.name}")

    try:
        from atlas_services.telegram_reporter import send_message
        text = (
            f"Daily Report - {report['date']}\n\n"
            f"Serper: {metrics.get('serper_found', 0)} emails\n"
            f"Playwright: {metrics.get('pw_found', 0)} companies\n"
            f"Enriched: {metrics.get('enriched', 0)}\n"
            f"Ready: {metrics.get('filtered', 0)}\n"
            f"Indo Started: {metrics.get('indo_started', 0)}\n"
            f"Indo Follow-ups: {metrics.get('indo_followups', 0)}\n"
            f"Duration: {report['duration_s']}s"
        )
        send_message(text)
        log("[OK] Telegram")
    except Exception as e:
        log(f"[!] Telegram: {e}")


# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-finder", action="store_true")
    ap.add_argument("--skip-playwright", action="store_true")
    ap.add_argument("--skip-enrich", action="store_true")
    ap.add_argument("--skip-send", action="store_true")
    ap.add_argument("--enrich-limit", type=int, default=30)
    ap.add_argument("--daily-limit", type=int, default=20)
    a = ap.parse_args()

    log("")
    log("=" * 60)
    log(f"DAILY AUTO - {START.strftime('%Y-%m-%d %H:%M')} - {'DRY' if a.dry_run else 'REAL'}")
    log("=" * 60)

    m = {}
    if not preflight().get("ok"):
        log("[X] preflight failed")
        step_report({**m, "aborted": True})
        return 1

    # 1. Serper
    s1 = {"out": None, "count": 0}
    if not a.skip_finder:
        s1 = step_find_serper()
        m["serper_found"] = s1["count"]

    # 2. Playwright
    s2 = {"out": None, "count": 0}
    if not a.skip_finder and not a.skip_playwright:
        s2 = step_find_playwright()
        m["pw_found"] = s2["count"]

    # 3. Enrich
    enrich_target = s1["out"]
    if enrich_target and s2.get("out") and s2["out"].exists():
        try:
            base = json.loads(enrich_target.read_text(encoding="utf-8"))
            extra = json.loads(s2["out"].read_text(encoding="utf-8"))
            existing_emails = {c.get("email") for c in base.get("companies", [])
                               if c.get("email")}
            for c in extra.get("companies", []):
                if c.get("email") and c["email"] in existing_emails:
                    continue
                base.setdefault("companies", []).append(c)
            enrich_target.write_text(
                json.dumps(base, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception as e:
            log(f"[!] merge failed: {e}")

    if not a.skip_enrich and enrich_target:
        s3 = step_enrich(enrich_target, limit=a.enrich_limit)
        m["enriched"] = s3.get("count", 0)
        clean_src = s3.get("file", enrich_target)
    else:
        clean_src = enrich_target

    # 4. Clean
    s4 = step_clean(clean_src) if clean_src else {"file": None, "count": 0}
    m["cleaned"] = s4.get("count", 0)

    # 5. Filter
    s5 = step_filter(s4.get("file")) if s4.get("file") else \
        {"file": None, "count": 0}
    m["filtered"] = s5.get("count", 0)

    # 5.5 Check for Replies (Skipped for now)
    if not a.skip_send:
        log("")
        log("=" * 60)
        log("STEP 5.5: Checking for Replies (IMAP)")
        log("=" * 60)
        log("[i] Skipped: IMAP is not enabled. Please check Zoho manually.")

    # 6. Start Indoctrination
    if not a.skip_send:
        s6 = step_start_indoctrination(s5.get("file"), a.daily_limit, dry=a.dry_run)
        m["indo_started"] = s6.get("started", 0)

    # 7. Process Due (Follow-ups)
    s7 = step_process_due_indoctrination(dry=a.dry_run)
    m["indo_followups"] = s7.get("sent", 0) if isinstance(s7, dict) else 0

        # 7.5 Social Media Automation
    if False and not a.skip_send: # Disabled here. Handled by Task Scheduler 3x a day.
        log("")
        log("=" * 60)
        log("STEP 7.5: Social Media Automation")
        log("=" * 60)
        try:
            from atlas_services import social_engine
            soc_res = social_engine.run_daily_social(dry_run=a.dry_run)
            if soc_res.get("ok"):
                log("[OK] Social post generated and published.")
                m["social_posted"] = 1
            else:
                log(f"[!] Social post failed: {soc_res.get('reason')}")
        except Exception as e:
            log(f"[!] Social engine error: {e}")

    # 8. Report
    step_report(m)

    log("")
    log("=" * 60)
    log("DAILY AUTO COMPLETE")
    log("=" * 60)
    for k, v in m.items():
        log(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())