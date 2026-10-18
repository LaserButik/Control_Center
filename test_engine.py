import sys
sys.path.insert(0, '.')
from atlas_services import indoctrination_engine as engine

# 1. محاكاة إضافة عميل جديد (Dry Run)
print("--- 1. Starting sequence for test@example.com ---")
prospect = {
    "email": "test@example.com",
    "company_name": "Test Clinic",
    "contact_name": "John Doe"
}
res = engine.start_sequence(prospect, language="en", dry_run=True)
print(f"Result: {res}")

# 2. عرض الإحصائيات
print("\n--- 2. Current Stats ---")
print(engine.get_stats())

# 3. محاكاة مرور 1 يوم ومعالجة المستحقين
print("\n--- 3. Simulating processing due emails (should not send Day 1 yet) ---")
res2 = engine.process_due(dry_run=True)
print(f"Process Result: {res2}")

# ملاحظة: إذا أردت اختبار إرسال اليوم التالي، يمكنك فتح ملف
# data/email/indoctrination_state.json وتغيير تاريخ last_sent_at ليكون قبل يومين.