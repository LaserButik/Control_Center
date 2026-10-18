# -*- coding: utf-8 -*-
"""
AI Mentors Agency — LinkedIn Automation Engine (Human Emulation)
"""

import asyncio
import random
import json
import urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
PROSPECTS_FILE = BASE_DIR / "data" / "prospects" / "ready_to_send.json"
SESSION_DIR = BASE_DIR / "linkedin_session"

# الكلمات المفتاحية لصناع القرار
DECISION_MAKER_KEYWORDS = [
    "owner", "founder", "ceo", "manager", "director", "doctor", "dentist", 
    "partner", "chief", "head of", "president", "specialist", "surgeon", "consultant",
    "مالك", "مؤسس", "مدير", "طبيب", "رئيس", "أخصائي", "استشاري", "جراح"
]

async def human_delay(min_s=5, max_s=12):
    """تأخير عشوائي طويل ليحاكي تفكير الإنسان"""
    await asyncio.sleep(random.uniform(min_s, max_s))

async def human_scroll(page):
    """تمرير الصفحة بشكل عشوائي"""
    for _ in range(random.randint(1, 3)):
        scroll_amount = random.randint(200, 500)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(1.0, 2.5))

async def close_popups(page):
    """إغلاق النوافذ المزعجة"""
    try:
        dismiss_btns = page.locator("button[aria-label='Dismiss'], button[aria-label='إغلاق'], button:has-text('Ignore')")
        count = await dismiss_btns.count()
        if count > 0:
            for i in range(count):
                await dismiss_btns.nth(i).click()
                await asyncio.sleep(1)
    except:
        pass

async def find_and_click_connect(page):
    """البحث عن زر التواصل بطرق متعددة"""
    # 1. التأكد أنه ليس قيد الانتظار
    pending_msg = page.locator("span:has-text('Pending'), span:has-text('قيد الانتظار')").first
    if await pending_msg.is_visible():
        return "pending"

    # 2. زر التواصل المباشر (عربي أو إنجليزي)
    direct_btn = page.locator("button:has-text('Connect'), button:has-text('تواصل')").first
    if await direct_btn.is_visible():
        await direct_btn.click()
        return "clicked"

    # 3. زر التواصل المخفي تحت "المزيد" (More)
    more_btn = page.locator("button[aria-label='More actions'], button[aria-label='المزيد من الإجراءات'], button:has-text('More'), button:has-text('المزيد')").first
    if await more_btn.is_visible():
        await more_btn.click()
        await asyncio.sleep(2) # انتظار فتح القائمة
        
        dropdown_connect = page.locator("div[role='menu'] div[role='button']:has-text('Connect'), div[role='menu'] div[role='button']:has-text('تواصل')").first
        if await dropdown_connect.is_visible():
            await dropdown_connect.click()
            return "clicked"
            
    return "not_found"

async def run_linkedin_outreach(max_connections=10):
    print(f"🚀 Starting Human-Like Outreach (Max: {max_connections})...")

    if not PROSPECTS_FILE.exists():
        print(f"❌ File not found: {PROSPECTS_FILE}")
        return

    data = json.loads(PROSPECTS_FILE.read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    
    junk_words = ["contact", "archives", "about", "definition", "meaning", "in abu dhabi", "in dubai", "agents", "clinic in", "law firm in", "salon abu dhabi"]
    valid_companies = [
        c for c in companies 
        if c.get("company_name") and not any(x in c.get("company_name").lower() for x in junk_words)
    ]
    
    print(f"✅ Found {len(valid_companies)} valid companies.")
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        print("🌐 Opening browser (Slow & Steady)...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # التوجه للصفحة الرئيسية
        await page.goto("https://www.linkedin.com/feed/")
        await asyncio.sleep(5)
        
        if "login" in page.url:
            print("🛑 Please log in manually. You have 180 seconds...")
            await asyncio.sleep(180)
            if "login" in page.url:
                print("❌ Login timeout.")
                await context.close()
                return
        
        print("✅ Logged in successfully!\n")
        
        count = 0
        for c in valid_companies:
            if count >= max_connections:
                break
                
            company_name = c.get("company_name")
            print(f"🔍 Searching for: {company_name}")
            
            encoded_name = urllib.parse.quote(company_name)
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_name}"
            
            await page.goto(search_url)
            
            # انتظار طويل جداً لتحميل الصفحة (محاكاة قراءة الإنسان)
            print("   ⏳ Waiting for page to load like a human...")
            await asyncio.sleep(random.uniform(7, 12))
            
            # تمرير الصفحة
            await human_scroll(page)
            await close_popups(page)
            
            # محاولة إيجاد زر "تواصل" مباشرة في صفحة البحث
            found_directly = False
            try:
                # البحث عن أي زر "تواصل" في النتائج
                connect_buttons = page.locator("button:has-text('Connect'), button:has-text('تواصل')")
                btn_count = await connect_buttons.count()
                
                if btn_count > 0:
                    # يوجد زر تواصل مباشر! سنضغط عليه
                    await connect_buttons.first.click()
                    print("   ✅ Found direct Connect button in search results.")
                    
                    # التعامل مع النافذة المنبثقة (إضافة ملاحظة أم لا)
                    await asyncio.sleep(3)
                    try:
                        add_note_btn = page.locator("button:has-text('Add a note'), button:has-text('إضافة ملاحظة')")
                        await add_note_btn.wait_for(state="visible", timeout=4000)
                        await add_note_btn.click()
                        await asyncio.sleep(2)
                        
                        # كتابة ملاحظة قصيرة
                        await page.locator("textarea[name='message']").fill(f"Hi, I came across {company_name} and would love to connect!")
                        await asyncio.sleep(2)
                        await page.locator("button:has-text('Send'), button:has-text('إرسال')").first.click()
                        print("   ✅ Sent WITH note.")
                    except:
                        try:
                            await page.locator("button:has-text('Send without a note'), button:has-text('إرسال بدون ملاحظة')").first.click()
                            print("   ✅ Sent WITHOUT note.")
                        except:
                            print("   ✅ Connection request sent directly.")
                    
                    count += 1
                    found_directly = True
                    await human_delay(15, 25) # انتظار طويل قبل الانتقال للشركة التالية
                    
            except Exception as e:
                print(f"   ⏭️ No direct Connect button. Trying to open profiles...")
                found_directly = False
                
            # إذا لم نجد زر تواصل مباشر، نبحث في الملفات الشخصية
            if not found_directly:
                try:
                    # العثور على روابط الأشخاص في منتصف الشاشة (وليس القوائم الجانبية)
                    # نستخدم xpath للبحث عن الروابط داخل حاوية النتائج الرئيسية
                    profile_links = await page.locator("main a[href*='/in/']").all()
                    
                    if not profile_links:
                        print(f"   ⏭️ No profiles found for {company_name}.")
                        continue
                        
                    # نقوم بفحص أول 5 ملفات شخصية فقط
                    for link in profile_links[:5]:
                        try:
                            # الانتقال للملف الشخصي
                            await link.click()
                            await asyncio.sleep(random.uniform(5, 8)) # قراءة الملف
                            await human_scroll(page)
                            
                            # قراءة اسم الشخص
                            name_element = page.locator("h1")
                            if await name_element.is_visible():
                                person_name = await name_element.inner_text()
                                print(f"   -> Checking profile: {person_name.strip()}")
                            
                            # محاولة الضغط على تواصل
                            result = await find_and_click_connect(page)
                            
                            if result == "clicked":
                                await asyncio.sleep(3)
                                try:
                                    add_note_btn = page.locator("button:has-text('Add a note'), button:has-text('إضافة ملاحظة')")
                                    await add_note_btn.wait_for(state="visible", timeout=4000)
                                    await add_note_btn.click()
                                    await asyncio.sleep(2)
                                    await page.locator("textarea[name='message']").fill(f"Hi, I came across your profile and would love to connect!")
                                    await asyncio.sleep(2)
                                    await page.locator("button:has-text('Send'), button:has-text('إرسال')").first.click()
                                    print("   ✅ Sent WITH note.")
                                except:
                                    try:
                                        await page.locator("button:has-text('Send without a note'), button:has-text('إرسال بدون ملاحظة')").first.click()
                                        print("   ✅ Sent WITHOUT note.")
                                    except:
                                        print("   ✅ Request sent.")
                                
                                count += 1
                                await human_delay(15, 25)
                                break # ننتقل للشركة التالية بعد النجاح
                                
                            elif result == "pending":
                                print("   ⏭️ Already pending.")
                                break # ننتقل للشركة التالية
                                
                            else:
                                # لم نجد زر تواصل، نرجع لصفحة البحث
                                await page.go_back()
                                await asyncio.sleep(random.uniform(4, 7))
                                
                        except Exception as inner_e:
                            # إذا حدث خطأ في فتح الملف، نرجع لصفحة البحث
                            print(f"   ⚠️ Skipping profile due to error.")
                            try:
                                await page.go_back()
                                await asyncio.sleep(3)
                            except:
                                pass
                            continue
                            
                except Exception as e:
                    print(f"   ⚠️ Error processing search results: {e}")
                    continue
        
        print(f"\n🎉 Outreach Complete! Total requests sent: {count}")
        await context.close()

if __name__ == "__main__":
    # بدأنا بـ 10 طلبات فقط لضمان الأمان
    asyncio.run(run_linkedin_outreach(max_connections=10))