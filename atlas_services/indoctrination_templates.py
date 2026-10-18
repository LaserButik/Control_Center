# -*- coding: utf-8 -*-
"""Indoctrination Sequence — 5 emails to build authority and trust."""

from __future__ import annotations

import html
import re

# ══════════════════════════════════════════════════════════════════
# Campaign Constants
# ══════════════════════════════════════════════════════════════════
PHYSICAL_ADDRESS = "AI Mentors Agency, Business Bay, Dubai, UAE"
SENDER_NAME = "Saleh Haidar"
SENDER_TITLE = "Founder, AI Mentors Agency"
SENDER_EMAIL = "info@salehhaidar.com"
SENDER_PHONE = "+971 502 889 414"
UNSUBSCRIBE_EN = "Reply STOP to unsubscribe."
UNSUBSCRIBE_AR = "لإلغاء، ردّوا بكلمة STOP. Reply STOP to unsubscribe."

ALPHA_URL = "https://46-101-220-218.sslip.io/alpha"
CALENDLY_LINK = "https://calendly.com/salehhaidar/15min"

CATEGORIES = (
    "day0_truth",
    "day1_struggle",
    "day3_proof",
    "day5_mission",
    "day7_invitation",
)

# ══════════════════════════════════════════════════════════════════
# Content — (Subject, Paragraph 1, Paragraph 2, CTA)
# ══════════════════════════════════════════════════════════════════
_CONTENT = {
    # ── EMAIL 1: THE TRUTH ──
    ("en", "day0_truth"): (
        "The truth about business, AI, and starting from zero",
        "My name is Saleh Haidar. I'm not a tech guru selling you a dream.",
        "I'm an author, a mentor, and a businessman. I left my home country due to war. I moved to an Arab country and started from zero. Then I moved to a European country and started from zero again. After 9 years, I moved to the Gulf and started from zero a 4th time. I faced debts, language barriers, and severe financial pressure. But I didn't give up. I educated myself (Google, IBM, INSEAD), wrote books like 'The Art of Achieving Balance', and built real AI systems. Let me share my journey with you.",
        "Read my story and test my actual system here: {alpha_url}",
    ),
    ("ar", "day0_truth"): (
        "الحقيقة عن الأعمال، الذكاء الاصطناعي، والبدء من الصفر",
        "اسمي صالح حيدر. أنا لست خبير تكنولوجيا يبيعك حلماً.",
        "أنا مؤلف، مدرب، ورجل أعمال. تركت بلدي الأم بسبب الحرب. انتقلت إلى بلد عربي وبدأت من الصفر. ثم انتقلت إلى دولة أوروبية وبدأت من الصفر مرة أخرى. بعد 9 سنوات، انتقلت إلى الخليج وبدأت من الصفر للمرة الرابعة. واجهت الديون، وصعوبات تعلم اللغات الجديدة، والضغوط المالية الشديدة. لكنني لم أستسلم. تعلمت وطورت نفسي (شهادات من Google, IBM, INSEAD)، وألفت كتباً مثل 'فن تحقيق التوازن'، وبنيت أنظمة ذكاء اصطناعي حقيقية. دعني أشاركك رحلتي.",
        "اقرأ قصتي وجرّب نظامي الحقيقي من هنا: {alpha_url}",
    ),
    # ── EMAIL 2: THE STRUGGLE ──
    ("en", "day1_struggle"): (
        "From debts and 4 failed starts to building AI systems",
        "Before I built AI Mentors Agency, I went through severe financial pressure.",
        "I failed. Then I failed again. 4 different times in 4 different places. I worked jobs, had debts, and people were chasing me for money. I had to adapt to new cultures and learn new languages from scratch. I felt like I was failing. But I started teaching myself. I read books, took courses, and built my first system. The fourth time, it worked. Today, my system runs 14 AI agents. I share this because I know what it feels like to lose customers you can't reach.",
        "See the system I built myself: {alpha_url}",
    ),
    ("ar", "day1_struggle"): (
        "من الديون و4 محاولات فاشلة إلى بناء أنظمة ذكاء اصطناعي",
        "قبل أن أبني AI Mentors Agency، مررت بضغوط مالية شديدة.",
        "فشلت. ثم فشلت مرة أخرى. 4 مرات في 4 أماكن مختلفة. عملت في وظائف، وكانت لدي ديون، والناس تطالبني بالمال. اضطررت للتأقلم مع ثقافات جديدة وتعلم لغات من الصفر. شعرت أنني أفشل. لكنني بدأت أتعلم بنفسي. قرأت كتباً، وحضرت دورات، وبنيت نظامي الأول. في المرة الرابعة، نجح الأمر. اليوم، نظامي يدير 14 وكيلاً ذكياً. أشاركك هذا لأنني أعرف كيف يبدو الشعور بأن عملك يخسر عملاء لا تستطيع الوصول إليهم.",
        "شاهد النظام الذي بنيته بنفسي: {alpha_url}",
    ),
    # ── EMAIL 3: THE PROOF ──
    ("en", "day3_proof"): (
        "What I built (and what it can do for you)",
        "In my last email, I told you I built a system. Here's exactly what it does.",
        "ALPHA is an AI WhatsApp employee that replies to your customers 24/7 in Arabic and English. It books appointments and qualifies leads. JARVIS is an executive operator that runs complete marketing campaigns. Behind them are 14 specialized agents working as one team. This isn't a pitch deck. This is a real system, built by me (143 tools, 161 functions, and 149 passing tests).",
        "You can test it yourself: {alpha_url}",
    ),
    ("ar", "day3_proof"): (
        "ما الذي بنيته وماذا يمكنه أن يفعل لك",
        "في الإيميل السابق، أخبرتك أنني بنيت نظاماً. إليك ما يفعله بالضبط.",
        "ALPHA هو موظف واتساب ذكي يرد على عملائك 24/7 بالعربية والإنجليزية، ويحجز المواعيد ويؤهل العملاء. JARVIS هو مشغّل تنفيذي يدير حملات تسويقية كاملة. خلفهما 14 وكيلاً متخصصاً يعملون كفريق واحد. هذا ليس عرضاً تقديمياً. هذا نظام حقيقي، بنيته بيدي (143 أداة، 161 دالة، و149 اختباراً ناجحاً).",
        "يمكنك تجربته بنفسك: {alpha_url}",
    ),
    # ── EMAIL 4: THE MISSION ──
    ("en", "day5_mission"): (
        "Why I help people (even when it doesn't pay)",
        "I run a group of over 400 people under the 'Make Your Destiny' initiative.",
        "Over the years, I've helped them for free. We held meetings, took on challenges, and many of them started their own businesses and changed their lives. I didn't do it for money. I did it because I was in their shoes once — in my home country, then in an Arab country, then in Europe, then in the Gulf. Today, my goal isn't just to sell a system. My goal is to help businesses stop losing customers due to delayed replies.",
        "If you want to be part of this, start by testing the system: {alpha_url}",
    ),
    ("ar", "day5_mission"): (
        "لماذا أساعد الناس (حتى عندما لا يدفعون)",
        "أنا مسؤول عن مجموعة فيها أكثر من 400 شخص تحت مبادرة 'اصنع قدرك'.",
        "خلال السنوات الماضية، ساعدتهم مجاناً. عملنا لقاءات، دخلنا تحديات، وكثير منهم بدأ مشاريعه الخاصة وتغيرت حياته. لم أفعل ذلك من أجل المال. فعلته لأنني كنت في مكانهم يوماً ما، في بلدي الأم، ثم في بلد عربي، ثم في أوروبا، ثم في الخليج. اليوم، هدفي ليس فقط بيع نظام. هدفي هو أن أساعد الشركات على التوقف عن خسارة العملاء بسبب الردود المتأخرة.",
        "إذا كنت تريد أن تكون جزءاً من هذا، ابدأ بتجربة النظام: {alpha_url}",
    ),
    # ── EMAIL 5: THE INVITATION ──
    ("en", "day7_invitation"): (
        "A personal invitation for {company_name}",
        "I've shared my story, what I built, and why I do this.",
        "Now, the decision is yours. If you want to see how ALPHA can help {company_name} recover the customers you're losing every night, book a quick call with me. Or, if you prefer to try it first, the system is ready.",
        "No pressure. No pitch. Book a call here: {calendly_link}",
    ),
    ("ar", "day7_invitation"): (
        "دعوة شخصية لـ {company_name}",
        "لقد شاركتك قصتي، وما بنيته، ولماذا أفعل هذا.",
        "الآن، القرار لك. إذا كنت تريد أن ترى كيف يمكن لـ ALPHA أن يساعد {company_name} على استعادة العملاء الذين يخسرهم كل ليلة، احجز مكالمة سريعة معي. أو، إذا كنت تفضل التجربة أولاً، النظام جاهز.",
        "لا ضغط. لا بيع. احجز مكالمة من هنا: {calendly_link}",
    ),
}

_GREETING = {"en": "Hi {contact_name},", "ar": "مرحبا {contact_name}،"}
_SIGNOFF = {"en": "Best regards,", "ar": "مع التحية،"}

_PRIMARY = "#667eea"
_FOOTER = "#2d3748"
_TEXT = "#2d3748"

def _plain(lang, p1, p2, cta) -> str:
    return "\n\n".join([
        _GREETING[lang],
        p1,
        p2,
        cta,
        "%s\n{sender_name}\n{sender_title}\n{sender_email} | {sender_phone}"
        % _SIGNOFF[lang],
        "--\n{unsubscribe_line}\n{physical_address}",
    ])

def _build_html_body(lang, t, plain):
    direction = "rtl" if lang == "ar" else "ltr"
    align = "right" if lang == "ar" else "left"
    font = ("Tahoma, Arial, sans-serif" if lang == "ar"
            else "Arial, Helvetica, sans-serif")

    def para(text_template, extra=""):
        # 1. استبدال المتغيرات مثل {contact_name}
        text = str(text_template).format_map(plain)

        # 2. إخفاء الروابط مؤقتاً لتجنب مشاكل التشفير
        urls = re.findall(r'(https?://[^\s<"]+)', text)
        for i, url in enumerate(urls):
            text = text.replace(url, f"__URL_{i}__")

        # 3. تشفير النص
        safe_text = html.escape(text)

        # 4. استبدال الروابط بالأزرار
        for i, url in enumerate(urls):
            button_text = "Test ALPHA Now &rarr;" if lang == "en" else "جرّب ALPHA الآن &larr;"
            if "calendly" in url:
                button_text = "Book a Meeting &rarr;" if lang == "en" else "احجز اجتماعاً &larr;"

            safe_url = html.escape(url, quote=True)

            button_html = (f'<div style="margin: 24px 0;">'
                           f'<a href="{safe_url}" style="display:inline-block;padding:14px 28px;'
                           f'background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);'
                           f'color:#ffffff;text-decoration:none;border-radius:8px;'
                           f'font-weight:bold;font-size:16px;'
                           f'box-shadow: 0 4px 12px rgba(102,126,234,0.4);">'
                           f'{button_text}</a></div>')

            safe_text = safe_text.replace(f"__URL_{i}__", button_html)

        return ('<p style="margin:0 0 14px;font-size:15px;line-height:1.7;'
                'color:%s;%s">%s</p>'
                % (_TEXT, extra, safe_text))

    return "".join([
        '<!DOCTYPE html><html lang="%s" dir="%s"><head>' % (lang, direction),
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>AI Mentors Agency</title></head>',
        '<body style="margin:0;padding:0;background:#f4f6fa;">',
        '<table role="presentation" width="100%%" cellpadding="0" '
        'cellspacing="0" style="width:100%%;background:#f4f6fa;'
        'padding:20px 10px;" dir="%s"><tr><td align="center">' % direction,
        '<table role="presentation" width="600" cellpadding="0" '
        'cellspacing="0" style="width:100%%;max-width:600px;background:'
        '#ffffff;border:1px solid #e5e9f2;border-radius:10px;font-family:%s;'
        'text-align:%s;" dir="%s">' % (font, align, direction),
        '<tr><td style="padding:18px 22px;background:%s;color:#ffffff;'
        'font-size:18px;font-weight:bold;">AI Mentors Agency</td></tr>'
        % _PRIMARY,
        '<tr><td style="padding:23px 22px;">',
        para(_GREETING[lang]),
        para(t["p1"]),
        para(t["p2"]),
        para(t["cta"], 'font-weight:bold;margin-top:18px;margin-bottom:12px;'),
        para("%s\n{sender_name}\n{sender_title}\n{sender_email} | "
             "{sender_phone}" % _SIGNOFF[lang]),
        '</td></tr>',
        '<tr><td style="background:%s;padding:18px 22px;color:#cbd5e0;'
        'font-size:12px;line-height:1.7;text-align:%s;">'
        '%s<br>%s</td></tr>'
        % (_FOOTER, align, html.escape(plain["unsubscribe_line"]), html.escape(plain["physical_address"])),
        '</table></td></tr></table></body></html>',
    ])

def _build() -> dict:
    out = {"en": [], "ar": []}
    for lang in ("en", "ar"):
        for cat in CATEGORIES:
            subject, p1, p2, cta = _CONTENT[(lang, cat)]
            out[lang].append({
                "id": "indoctrination_%s_%s" % (lang, cat),
                "category": cat,
                "language": lang,
                "subject": subject,
                "p1": p1,
                "p2": p2,
                "cta": cta,
                "body": _plain(lang, p1, p2, cta)
            })
    return out

TEMPLATES = _build()

def get_sequence(language: str) -> list:
    return [dict(t) for t in TEMPLATES.get(language, [])]

def get_template_by_id(template_id: str):
    for lang_items in TEMPLATES.values():
        for t in lang_items:
            if t["id"] == template_id:
                return dict(t)
    return None

class _Fill(dict):
    def __missing__(self, key):
        return ""

def _clean(value) -> str:
    return " ".join(str(value or "").split())

def unsubscribe_line(language, unsubscribe_url="") -> str:
    line = UNSUBSCRIBE_AR if language == "ar" else UNSUBSCRIBE_EN
    if unsubscribe_url:
        line += (" أو: %s" if language == "ar" else " Or: %s") \
                % unsubscribe_url
    return line

def render(template, prospect, *,
           sender_name=SENDER_NAME,
           sender_title=SENDER_TITLE,
           sender_email=SENDER_EMAIL,
           sender_phone=SENDER_PHONE,
           physical_address=PHYSICAL_ADDRESS,
           alpha_url=ALPHA_URL,
           calendly_link=CALENDLY_LINK,
           unsubscribe_url="") -> dict:
    t = template or {}
    p = prospect if isinstance(prospect, dict) else {}
    lang = t.get("language") or "en"

    company = _clean(p.get("company_name"))
    contact = _clean(p.get("contact_name"))
    if not contact:
        if company:
            contact = ("فريق %s" % company if lang == "ar"
                       else "%s team" % company)
        else:
            contact = "بكم" if lang == "ar" else "there"
    if not company:
        company = "فريقكم" if lang == "ar" else "your team"

    template_id = t.get("id", "unknown")
    utm_suffix = f"?utm_source=email&utm_medium=indoctrination&utm_campaign={template_id}"

    tracked_alpha_url = alpha_url + utm_suffix
    tracked_calendly_link = (calendly_link or CALENDLY_LINK) + utm_suffix

    values = {
        "company_name": company,
        "contact_name": contact,
        "alpha_url": tracked_alpha_url,
        "calendly_link": tracked_calendly_link,
        "sender_name": _clean(sender_name) or SENDER_NAME,
        "sender_title": _clean(sender_title) or SENDER_TITLE,
        "sender_email": _clean(sender_email) or SENDER_EMAIL,
        "sender_phone": _clean(sender_phone) or SENDER_PHONE,
        "physical_address": _clean(physical_address) or PHYSICAL_ADDRESS,
        "unsubscribe_line": unsubscribe_line(lang, unsubscribe_url),
    }

    plain = _Fill(values)

    # بناء النص العادي
    body_plain = _plain(lang, t.get("p1", ""), t.get("p2", ""), t.get("cta", ""))

    # بناء النص HTML
    html_body = _build_html_body(lang, t, plain)

    return {
        "subject": str(t.get("subject", "")).format_map(plain),
        "body": str(body_plain).format_map(plain),
        "body_html": html_body,
        "unsubscribe_line": values["unsubscribe_line"],
    }