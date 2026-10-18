"""Build/update seen.json from all finder files + sent log."""
import json
from pathlib import Path
from urllib.parse import urlparse

CC = Path(__file__).resolve().parent
PROSPECTS = CC / "data" / "prospects"
SEEN = PROSPECTS / "seen.json"

emails, domains, names, phones = set(), set(), set(), set()

# 1. كل ملفات finder
for f in PROSPECTS.glob("finder_*.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        for c in data.get("companies", []):
            if c.get("email"):
                emails.add(c["email"].strip().lower())
            if c.get("website"):
                h = urlparse(c["website"]).netloc.lower().replace("www.", "")
                if h:
                    domains.add(h)
            if c.get("company_name"):
                names.add(c["company_name"].strip().lower())
            if c.get("phone_e164"):
                phones.add(c["phone_e164"].strip())
    except Exception as e:
        print(f"skip {f.name}: {e}")

# 2. سجل الإرسال
log = CC / "data" / "email" / "sent_log.jsonl"
if log.exists():
    for line in log.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                e = json.loads(line)
                if e.get("email"):
                    emails.add(e["email"].strip().lower())
            except Exception:
                pass

SEEN.write_text(
    json.dumps({
        "emails": sorted(emails),
        "domains": sorted(domains),
        "names": sorted(names),
        "phones": sorted(phones),
    }, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"✅ seen.json updated")
print(f"📧 Emails:  {len(emails)}")
print(f"🌐 Domains: {len(domains)}")
print(f"📝 Names:   {len(names)}")
print(f"📞 Phones:  {len(phones)}")
print(f"💾 {SEEN}")