"""
Run Finder, filter against seen.json, save only NEW companies.
"""
import subprocess
import json
from pathlib import Path
from urllib.parse import urlparse

CC = Path(r"C:\Users\butik\Documents\Control_Center")
PROSPECTS = CC / "data" / "prospects"

# 1. شغّل Finder
print("🔍 تشغيل Finder...\n")
cmd = [
    str(CC / "venv" / "Scripts" / "python.exe"),
    "-m", "atlas_services.prospect_finder",
    "--all-sectors",
    "--country", "AE",
    "--mode", "serper",
    "--max", "20",
]
result = subprocess.run(cmd, cwd=str(CC), capture_output=True, text=True)
if result.returncode != 0:
    print("STDERR:", result.stderr[-500:])
    exit(1)
print(result.stdout[-800:])

# 2. اقرأ آخر ملف
files = sorted(PROSPECTS.glob("finder_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)
latest = files[0]
print(f"\n📂 {latest.name}")

data = json.loads(latest.read_text(encoding="utf-8"))

# 3. حمّل seen
seen_file = PROSPECTS / "seen.json"
seen = json.loads(seen_file.read_text(encoding="utf-8")) if seen_file.exists() else {}
seen_emails = {e.lower() for e in seen.get("emails", [])}
seen_names = {n.lower() for n in seen.get("names", [])}
seen_domains = {d.lower() for d in seen.get("domains", [])}

# 4. صفّي
fresh = []
skipped = []
for c in data.get("companies", []):
    email = (c.get("email") or "").strip().lower()
    name = (c.get("company_name") or "").strip().lower()
    sector = (c.get("sector") or "").strip().lower()
    website = c.get("website") or ""
    
    host = ""
    if website:
        host = urlparse(website).netloc.lower().replace("www.", "")

    if not email:
        skipped.append((name, "no_email"))
        continue
    if sector == "unknown":
        skipped.append((name, "unknown_sector"))
        continue
    if email in seen_emails or name in seen_names or (host and host in seen_domains):
        skipped.append((name, "seen"))
        continue
    fresh.append(c)

# 5. احفظ
data["companies"] = fresh
out = PROSPECTS / "fresh_to_send.json"
out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
               encoding="utf-8")

# 6. حدّث seen
for c in fresh:
    if c.get("email"): seen_emails.add(c["email"].lower())
    if c.get("company_name"): seen_names.add(c["company_name"].lower())
    if c.get("website"):
        h = urlparse(c["website"]).netloc.lower().replace("www.", "")
        if h: seen_domains.add(h)

seen["emails"] = sorted(seen_emails)
seen["names"] = sorted(seen_names)
seen["domains"] = sorted(seen_domains)
seen_file.write_text(json.dumps(seen, ensure_ascii=False, indent=2),
                     encoding="utf-8")

# 7. تقرير
print("\n" + "="*60)
print(f"✅ شركات جديدة جاهزة:  {len(fresh)}")
print(f"⏭️  تم تخطيها:           {len(skipped)}")
print("="*60)
for n, r in skipped[:15]:
    print(f"  • {n[:45]:45} → {r}")
print(f"\n💾 {out}")
print(f"📚 seen.json: {len(seen['emails'])} emails, {len(seen['names'])} names")