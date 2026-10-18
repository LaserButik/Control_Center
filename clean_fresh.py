"""
Clean fresh_to_send.json by removing low-quality entries.
"""
import json
import re
from pathlib import Path

CC = Path(r"C:\Users\butik\Documents\Control_Center")
src = CC / "data" / "prospects" / "fresh_to_send.json"

data = json.loads(src.read_text(encoding="utf-8"))
companies = data.get("companies", [])

# كلمات تدل على "ليس شركة"
BAD_WORDS = [
    "chatbot", "bot for", "how to", "guide", "tutorial",
    "why ", "best ", "top 10", "review", "article",
    "blog", "free ", "download", "app for", "telegram",
    "whatsapp business", "messenger",
]

# تطبيقات ومواقع معروفة
KNOWN_APPS = [
    "telegram", "whatsapp", "facebook", "instagram",
    "twitter", "youtube", "google", "microsoft",
    "apple", "amazon", "netflix",
]

# إيميلات مرفوضة (مزودين مجانيين)
BAD_EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "live.com", "aol.com",
    "icloud.com", "protonmail.com",
]

def is_bad(c):
    name = (c.get("company_name") or "").strip().lower()
    email = (c.get("email") or "").strip().lower()
    
    # اسم طويل جداً (عنوان)
    if len(name) > 50:
        return True, "long_title"
    
    # اسم فارغ
    if len(name) < 3:
        return True, "empty_name"
    
    # كلمات ممنوعة
    for w in BAD_WORDS:
        if w in name:
            return True, f"contains:{w}"
    
    # تطبيقات معروفة
    for app in KNOWN_APPS:
        if name == app or name.startswith(app + " "):
            return True, f"known_app:{app}"
    
    # إيميل مجاني
    if email:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain in BAD_EMAIL_DOMAINS:
            return True, f"free_email:{domain}"
    
    return False, None

good = []
bad = []
for c in companies:
    is_b, reason = is_bad(c)
    if is_b:
        bad.append((c.get("company_name", "?"), reason))
    else:
        good.append(c)

# احفظ
data["companies"] = good
out = CC / "data" / "prospects" / "fresh_cleaned.json"
out.write_text(json.dumps(data, ensure_ascii=False, indent=2),
               encoding="utf-8")

print(f"Before:  {len(companies)}")
print(f"Good:    {len(good)}")
print(f"Removed: {len(bad)}")
print()
for n, r in bad:
    print(f"  • {n[:50]:50} → {r}")
print()
print(f"Saved: {out}")