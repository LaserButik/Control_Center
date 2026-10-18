"""Clean enriched emails: remove placeholders + junk."""
import json
import re
from pathlib import Path

CC = Path(__file__).resolve().parent
PROSPECTS = CC / "data" / "prospects"
SOURCE = PROSPECTS / "playwright_enriched.json"

# نمط placeholder patterns
JUNK_EMAILS = {
    "you@email.com", "example@email.com", "johndoe@domain.com",
    "user@example.com", "test@test.com", "name@example.com",
    "your@email.com", "email@example.com",
}

# نمط junk domains
JUNK_DOMAINS = (
    "example.com", "example.org", "domain.com", "email.com",
    "yourdomain.com", "test.com",
)

# نهايات ملفات (صور)
ASSET_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js")

# إيميلات غير مناسبة
ROLE_MISMATCH = {
    "webmaster", "postmaster", "noreply", "no-reply",
    "donotreply", "abuse",
}

# دومينات حكومية/أدلة (ليست الشركة الفعلية)
BLOCKED_DOMAINS = (
    "dubailand.gov.ae", "healthfinder.ae", "startupsuae.com",
    "okadoc.com", "citysearch.ae", "propertyfinder.ae",
    "waze.com", "google.com", "yellowpages",
)


def is_junk_email(email: str) -> tuple[bool, str]:
    """Returns (is_junk, reason)."""
    if not email:
        return True, "empty"

    email = email.strip().lower()

    # placeholder كامل
    if email in JUNK_EMAILS:
        return True, "placeholder"

    # ملف صورة
    if email.endswith(ASSET_ENDINGS):
        return True, "asset_file"

    # pattern صورة
    if re.search(r"[a-f0-9]{20,}", email):  # hash طويل
        return True, "image_hash"

    # domain خاطئ
    domain = email.split("@")[-1] if "@" in email else ""
    if domain in JUNK_DOMAINS:
        return True, "junk_domain"

    # دور غير مناسب
    local = email.split("@")[0] if "@" in email else ""
    if local in ROLE_MISMATCH:
        return True, f"role:{local}"

    # دومين محجوب
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return True, f"blocked:{blocked}"

    # اسم placeholder
    if local in ("you", "example", "name", "user", "your"):
        return True, f"name:{local}"

    return False, ""


def main():
    if not SOURCE.exists():
        print(f"❌ {SOURCE} not found. Run enrich_playwright.py first.")
        return

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    print(f"📂 Loaded: {len(companies)} companies")

    good, junk = [], []
    for c in companies:
        email = (c.get("email") or "").strip()
        is_bad, reason = is_junk_email(email)
        if is_bad and email:
            junk.append((c.get("company_name", "?"), email, reason))
            c["email"] = None
            c["emails_all"] = []
        else:
            good.append(c)

    # احفظ الملف النظيف
    data["companies"] = companies
    out = PROSPECTS / "playwright_cleaned.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    # احفظ الملف الصالح فقط للإرسال
    data_clean = dict(data)
    data_clean["companies"] = [c for c in companies if c.get("email")]
    out_ready = PROSPECTS / "ready_to_send_v2.json"
    out_ready.write_text(
        json.dumps(data_clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # تقرير
    print(f"\n{'='*60}")
    print(f"✅ Clean emails: {len([c for c in companies if c.get('email')])}")
    print(f"❌ Junk removed: {len(junk)}")
    print(f"📧 Ready to send: {out_ready.name}")
    print(f"💾 Full cleaned: {out.name}")
    print(f"{'='*60}\n")

    if junk:
        print("🗑️  Removed emails:")
        for name, email, reason in junk:
            print(f"  • {name[:40]:40} | {email[:40]:40} | {reason}")


if __name__ == "__main__":
    main()