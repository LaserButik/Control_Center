import sys
from pathlib import Path

# إعداد المسارات
CC = Path(__file__).resolve().parent
sys.path.insert(0, str(CC))

from atlas_services.email_sender import EmailSender
from atlas_services import indoctrination_templates as indo_tpl

def main():
    # 1. بيانات العميل التجريبي (أنت)
    prospect = {
        "email": "butiklaser@gmail.com",
        "company_name": "Test Clinic Dubai",
        "contact_name": "Saleh"
    }

    # 2. جلب قالب الإيميل الأول (Day 0: The Truth)
    seq = indo_tpl.get_sequence("en")
    tpl = seq[0]

    # 3. تجهيز الإيميل وإضافة رابط التتبع
    rendered = indo_tpl.render(tpl, prospect)

    # 4. إرسال الإيميل الحقيقي
    print(f"Sending test email to {prospect['email']}...")
    sender = EmailSender(dry_run=False)
    
    # confirmed=True مطلوب للإرسال الحقيقي
    res = sender.send(prospect, rendered, template_id=tpl["id"], confirmed=True)
    
    print("\nResult:")
    print(res)

if __name__ == "__main__":
    main()