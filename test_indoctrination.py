import sys
sys.path.insert(0, '.')
from atlas_services.indoctrination_templates import get_sequence, render

# اختبار النسخة العربية
print("=" * 50)
print("ARABIC SEQUENCE TEST")
print("=" * 50)

ar_seq = get_sequence('ar')
prospect = {'company_name': 'عيادة كينيسيس', 'contact_name': 'أحمد'}

for i, t in enumerate(ar_seq, 1):
    rendered = render(t, prospect)
    print(f"\n--- EMAIL {i} ---")
    print(f"Subject: {rendered['subject']}")
    print(f"\n{rendered['body'][:400]}...\n") # طباعة أول 400 حرف

# اختبار النسخة الإنجليزية
print("\n" + "=" * 50)
print("ENGLISH SEQUENCE TEST")
print("=" * 50)

en_seq = get_sequence('en')
prospect_en = {'company_name': 'Kinesis Clinic', 'contact_name': 'Ahmed'}

for i, t in enumerate(en_seq, 1):
    rendered = render(t, prospect_en)
    print(f"\n--- EMAIL {i} ---")
    print(f"Subject: {rendered['subject']}")
    print(f"\n{rendered['body'][:400]}...\n")