import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from atlas_services import social_engine

if __name__ == "__main__":
    print("🚀 بدء اختبار توليد الصور بالذكاء الاصطناعي ونشرها...")
    # إجبار النظام على استخدام صور AI
    res = social_engine.run_daily_social(dry_run=False, image_mode="ai")
    
    print("\n--- النتيجة ---")
    print(f"Facebook: {res.get('facebook')}")
    print(f"LinkedIn: {res.get('linkedin')}")
    print("---------------")