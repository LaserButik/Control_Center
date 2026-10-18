# -*- coding: utf-8 -*-
"""Social Engine — Personal Brand & Authority Builder for Saleh Haidar."""

import base64
import json
import os
import random
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "social"
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR = DATA_DIR / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
POSTED_FILE = DATA_DIR / "posted_history.json"
LINKEDIN_TOKEN_FILE = DATA_DIR / "linkedin_token.json"

DUBAI_TZ = timezone(timedelta(hours=4))
ALPHA_URL = "https://46-101-220-218.sslip.io/alpha"

def _get_env(key):
    val = os.getenv(key, "").strip()
    if not val:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    return val

# استراتيجية المحتوى الجديدة: رحلة الهجرة، الكتب، الشهادات، والجمهور
PILLARS = [
    # 1. قصة الرحلة والهجرة (بدون ذكر أسماء الدول)
    "The Journey: I left my home country due to war. I moved to an Arab country and started from zero. Then to a European country, started from zero again. After 9 years, I moved to the Gulf, starting from zero a 4th time. I faced debts, language barriers, and severe pressure. But I built my AI agency, wrote my books, and became a mentor. Your current pain is your future strength.",
    
    # 2. الكتب والدورات (تسويق غير مباشر)
    "The Value: After 14 years of continuous learning and starting over, I wrote my books 'The Art of Achieving Balance' and 'Selling Your Ideas'. I also created the 'Professional Sales' course. I don't just talk about success; I teach the exact frameworks that helped me survive. What are you reading today?",
    
    # 3. الشهادات والخبرة (بناء السلطة)
    "The Proof: People ask how I built AI systems without a traditional tech background. The answer? Never stop learning. I hold certificates from IBM, Google, INSEAD, and the University of Michigan. Your background doesn't define your future; your hunger for knowledge does.",
    
    # 4. الذكاء الاصطناعي كأداة (ALPHA & JARVIS)
    "The Solution: I built ALPHA and JARVIS (14 AI agents). Why? Because I know how it feels to lose a customer at 11 PM because you are too exhausted. AI is not here to replace us; it's here to give us our time back so we can focus on strategy and family.",
    
    # 5. رسالة للجمهور (رواد الأعمال والمبتدئين)
    "To the struggling entrepreneur: I see you. I know the pressure of debts. I know the feeling of starting over in a new country. I've been in your shoes 4 times. Don't sell yourself short. Let's build your future together."
]

def generate_post(language: str, custom_pillar: str, platform: str) -> dict:
    api_key = _get_env("OPENAI_API_KEY").strip('"').strip("'")
    if not api_key:
        return {"ok": False, "reason": "OPENAI_API_KEY missing"}

    client = OpenAI(api_key=api_key)

    if language == "en":
        prompt = f"""
You are Saleh Haidar: an entrepreneur, author, mentor, and AI expert based in Dubai.
Write a highly engaging, VIRAL LinkedIn post based on this pillar: "{custom_pillar}"

Target Audience: Beginner entrepreneurs, SMEs, and people facing life struggles.

Formatting Rules (CRITICAL):
- Use 1-2 sentences per paragraph.
- Leave a blank line between EVERY paragraph.
- Use relevant emojis (📉, 🤖, 💼, 💡, 🚀, 🛑).
- Hook: A provocative or deeply relatable first line.
- Body: Share a story or a hard truth. NEVER mention specific countries (like Syria, Egypt, Europe). Use "my home country", "an Arab country", "a European country", "the Gulf".
- Value: Give one actionable tip or mind-blowing insight.
- Link Strategy: Do NOT put the ALPHA link in every post. Only include it if the post is specifically about AI. If you do include it, write: "Try ALPHA here: {ALPHA_URL}" at the VERY END.
- CTA: Ask them to DM you or comment. (e.g., "DM me 'GROWTH' and I'll send you a free chapter of my book").

MANDATORY HASHTAGS: End with 3-4 hashtags like:
#Saleh_Haidar #AI_Mentors_Agency #Entrepreneurship #Dubai

Tone: Direct, confident, empathetic, no-nonsense.
Language: English.
Output ONLY the post text.
"""
    else:
        prompt = f"""
أنت صالح حيدر: رائد أعمال، مؤلف، مدرب، وخبير ذكاء اصطناعي مقيم في الخليج.
اكتب منشور فيسبوك فيروسي ومؤثر بناءً على هذه الفكرة: "{custom_pillar}"

الجمهور المستهدف: رواد الأعمال المبتدئين، أصحاب الشركات الصغيرة، ومن يواجهون صعوبات في حياتهم.

قواعد التنسيق (مهم جداً):
- جملة أو جملتين في كل فقرة.
- اترك سطراً فارغاً بين كل فقرة.
- استخدم إيموجي مناسبة (📉, 🤖, 💼, 💡, 🚀, 🛑).
- بداية قوية: جملة صادمة أو واقعية تجذب الانتباه.
- المحتوى: اذكر قصتك (تركت بلدي الأم بسبب الحرب، انتقلت لبلد عربي، ثم أوروبي، ثم الخليج، وبدأت من الصفر 4 مرات، وواجهت صعوبات اللغة والديون). **لا تذكر أسماء الدول أبداً**.
- الفائدة: قدم نصيحة عملية أو ذكر كتابك/كورسك بشكل غير مباشر (مثال: "في كتابي فن تحقيق التوازن تحدثت عن هذا...").
- استراتيجية الرابط: **لا تضع رابط ALPHA في كل منشور**. فقط إذا كان المنشور عن الذكاء الاصطناعي، ضعه في النهاية كالتالي: "جرّب ALPHA من هنا: {ALPHA_URL}".
- الدعوة (CTA): اطلب منهم إرسال رسالة أو التعليق (مثال: "أرسل لي كلمة (تطوير) في الخاص وسأرسل لك فصلاً مجانياً من كتابي").

هاشتاغات إلزامية: يجب أن تنهي المنشور بـ:
#صالح_حيدر #AI_Mentors_Agency #ريادة_أعمال #دبي

الأسلوب: مباشر، واثق، متعاطف، بدون مجاملات.
Language: Arabic.
Output ONLY the post text.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        return {"ok": True, "content": content, "image_prompt": f"Professional, modern, high-tech visual representing: {custom_pillar}. Dark theme, cinematic lighting, 3D render style."}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def generate_ai_image(prompt: str) -> Path:
    api_key = _get_env("OPENAI_API_KEY").strip('"').strip("'")
    client = OpenAI(api_key=api_key)
    try:
        response = client.images.generate(
            model="gpt-image-1", 
            prompt=prompt,
            size="1024x1024",
            n=1,
        )
        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        filepath = IMAGE_DIR / f"ai_gen_{int(datetime.now().timestamp())}.png"
        with open(filepath, 'wb') as handler:
            handler.write(image_bytes)
        return filepath
    except Exception as e:
        print(f"AI Image generation failed: {e}")
        return None

def get_random_personal_image():
    images = list(IMAGE_DIR.glob("*.jpg")) + list(IMAGE_DIR.glob("*.jpeg")) + list(IMAGE_DIR.glob("*.png"))
    personal = [p for p in images if not p.name.startswith("ai_gen_")]
    if not personal: return None
    return random.choice(personal)

def post_to_facebook(content: str, image_path: Path = None) -> dict:
    page_id = _get_env("ALPHA_FB_PAGE_ID") or _get_env("META_FB_PAGE_ID")
    token = _get_env("META_PAGE_ACCESS_TOKEN") or _get_env("META_ACCESS_TOKEN")

    if not page_id or not token:
        return {"ok": False, "reason": "Missing Facebook credentials"}

    if image_path and image_path.exists():
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        payload = {"message": content, "access_token": token}
        try:
            with open(image_path, 'rb') as img:
                files = {'source': img}
                r = requests.post(url, data=payload, files=files, timeout=30)
                if r.status_code == 200:
                    return {"ok": True, "id": r.json().get("id")}
                return {"ok": False, "reason": r.text}
        except Exception as e:
            return {"ok": False, "reason": str(e)}
    else:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        payload = {"message": content, "access_token": token}
        try:
            r = requests.post(url, data=payload, timeout=15)
            if r.status_code == 200:
                return {"ok": True, "id": r.json().get("id")}
            return {"ok": False, "reason": r.text}
        except Exception as e:
            return {"ok": False, "reason": str(e)}

def post_to_linkedin(content: str, image_path: Path = None) -> dict:
    if not LINKEDIN_TOKEN_FILE.exists():
        return {"ok": False, "reason": "LinkedIn token missing."}

    token_data = json.loads(LINKEDIN_TOKEN_FILE.read_text(encoding="utf-8"))
    access_token = token_data.get("access_token")
    if not access_token:
        return {"ok": False, "reason": "Invalid token file"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    userinfo_url = "https://api.linkedin.com/v2/userinfo"
    r = requests.get(userinfo_url, headers=headers)
    if r.status_code != 200:
        return {"ok": False, "reason": f"Failed to get user info: {r.text}"}
    person_urn = f"urn:li:person:{r.json()['sub']}"

    media_asset = None
    if image_path and image_path.exists():
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
            }
        }
        reg_res = requests.post(register_url, headers=headers, json=register_payload)
        if reg_res.status_code == 200:
            reg_data = reg_res.json()
            upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            media_asset = reg_data["value"]["asset"]

            upload_headers = {"Authorization": f"Bearer {access_token}"}
            with open(image_path, 'rb') as img:
                requests.put(upload_url, headers=upload_headers, data=img)

    post_url = "https://api.linkedin.com/v2/ugcPosts"
    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": content},
                "shareMediaCategory": "IMAGE" if media_asset else "NONE"
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

    if media_asset:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {"status": "READY", "description": {"text": "Image"}, "media": media_asset, "title": {"text": "Image"}}
        ]

    try:
        r = requests.post(post_url, headers=headers, json=payload, timeout=15)
        if r.status_code == 201:
            return {"ok": True, "id": r.headers.get("x-restli-id")}
        return {"ok": False, "reason": r.text}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def run_daily_social(dry_run: bool = False, image_mode: str = "auto") -> dict:
    if dry_run:
        return {"ok": True, "reason": "dry_run"}

    current_pillar = random.choice(PILLARS)

    hour = datetime.now(DUBAI_TZ).hour
    if image_mode == "auto":
        if 6 <= hour < 12:
            current_image_mode = "ai"
        elif 12 <= hour < 16:
            current_image_mode = "personal"
        else:
            current_image_mode = "none"
    else:
        current_image_mode = image_mode

    # --- LinkedIn (English) ---
    en_res = generate_post("en", current_pillar, "linkedin")
    li_res = {"ok": False, "reason": "not attempted"}
    if en_res.get("ok"):
        img_path = None
        if current_image_mode == "ai":
            img_path = generate_ai_image(en_res["image_prompt"])
        elif current_image_mode == "personal":
            img_path = get_random_personal_image()
        li_res = post_to_linkedin(en_res["content"], img_path)

    # --- Facebook (Arabic) ---
    ar_res = generate_post("ar", current_pillar, "facebook")
    fb_res = {"ok": False, "reason": "not attempted"}
    if ar_res.get("ok"):
        img_path = None
        if current_image_mode == "ai":
            img_path = generate_ai_image(ar_res["image_prompt"])
        elif current_image_mode == "personal":
            img_path = get_random_personal_image()
        fb_res = post_to_facebook(ar_res["content"], img_path)

    history = []
    if POSTED_FILE.exists():
        try:
            history = json.loads(POSTED_FILE.read_text(encoding="utf-8"))
        except: pass
    history.append({
        "date": datetime.now(DUBAI_TZ).isoformat(),
        "image_mode": current_image_mode,
        "facebook_result": fb_res,
        "facebook_content": ar_res.get("content", ""),
        "linkedin_result": li_res,
        "linkedin_content": en_res.get("content", "")
    })
    POSTED_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "facebook": fb_res, "linkedin": li_res, "mode": current_image_mode}