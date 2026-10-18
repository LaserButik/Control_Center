"""Filter latest finder file: remove companies already sent + duplicates."""
import json
from pathlib import Path

CC = Path(__file__).resolve().parent
PROSPECTS = CC / "data" / "prospects"

# 1. جلب كل الإيميلات المُرسلة
sent_emails = set()

log = CC / "data" / "email" / "sent_log.jsonl"
if log.exists():
    for line in log.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                e = json.loads(line)
                email = (e.get("email") or "").strip().lower()
                if email and e.get("status") in ("sent", "dry_run"):
                    sent_emails.add(email)
            except json.JSONDecodeError:
                continue

state = CC / "data" / "email" / "prospect_state.json"
if state.exists():
    try:
        for email in json.loads(state.read_text(encoding="utf-8")).keys():
            sent_emails.add(email.strip().lower())
    except Exception:
        pass

print(f"📧 Emails already sent: {len(sent_emails)}")

# 2. أحدث ملف finder
files = sorted(PROSPECTS.glob("finder_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)
if not files:
    print("❌ No finder files.")
    raise SystemExit(1)

latest = files[0]
print(f"📂 Reading: {latest.name}")
data = json.loads(latest.read_text(encoding="utf-8"))
companies = data.get("companies", [])
print(f"📊 Total: {len(companies)}")

# 3. فلترة
new_list, skipped, seen_in_file = [], [], set()
for c in companies:
    email = (c.get("email") or "").strip().lower()
    name = c.get("company_name", "?")
    sector = (c.get("sector") or "").lower()

    if not email:
        skipped.append((name, "no_email"))
        continue
    if sector == "unknown":
        skipped.append((name, "unknown_sector"))
        continue
    if email in sent_emails:
        skipped.append((name, "already_sent"))
        continue
    if email in seen_in_file:
        skipped.append((name, "duplicate_in_file"))
        continue
    seen_in_file.add(email)
    new_list.append(c)

# 4. حفظ
data["companies"] = new_list
out = PROSPECTS / "ready_to_send.json"
out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
               encoding="utf-8")

print()
print("=" * 60)
print(f"✅ Ready: {len(new_list)}")
print(f"⏭️  Skipped: {len(skipped)}")
print("=" * 60)
for n, r in skipped:
    print(f"  • {n[:40]:40} → {r}")
print(f"\n💾 {out}")