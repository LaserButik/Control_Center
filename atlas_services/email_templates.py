# -*- coding: utf-8 -*-
"""ATLAS email templates — Cold Sequence with UTM tracking."""

from __future__ import annotations

import html
import re

# ══════════════════════════════════════════════════════════════════
# Campaign constants
# ══════════════════════════════════════════════════════════════════
PHYSICAL_ADDRESS = "AI Mentors Agency, Business Bay, Dubai, UAE"
SENDER_NAME = "Saleh Haidar"
SENDER_TITLE = "Founder, AI Mentors Agency"
SENDER_EMAIL = "info@salehhaidar.com"
SENDER_PHONE = "+971 502 889 414"
UNSUBSCRIBE_EN = "Reply STOP to unsubscribe."
UNSUBSCRIBE_AR = "للإلغاء، ردّوا بكلمة STOP. Reply STOP to unsubscribe."
MAX_WORDS = 100

ALPHA_URL = "https://46-101-220-218.sslip.io/alpha"
LEAD_MAGNET_BASE = "https://46-101-220-218.sslip.io/reports"
CALENDLY_LINK = "https://calendly.com/salehhaidar/15min"

CATEGORIES = (
    "day0_initial",
    "day1_value",
    "day3_proof",
    "day7_urgency",
    "day14_breakup",
)

DAY_OF = {
    "day0_initial": "day0",
    "day1_value": "day1",
    "day3_proof": "day3",
    "day7_urgency": "day7",
    "day14_breakup": "day14",
}

LANGUAGES = ("ar", "en")

INDUSTRY = {
    "clinics": {"en": "healthcare", "ar": "الرعاية الصحية"},
    "real_estate": {"en": "real estate", "ar": "العقارات"},
    "restaurants": {"en": "hospitality", "ar": "المطاعم"},
    "salons": {"en": "beauty", "ar": "التجميل"},
    "lawyers": {"en": "legal services", "ar": "الخدمات القانونية"},
}

SECTOR_PAIN = {
    "clinics": {
        "en": "patient messages that arrive after reception closes",
        "ar": "رسائل المرضى التي تصل بعد إغلاق الاستقبال",
        "magnet": "5 Patient Messages You Lose Every Night",
        "magnet_ar": "5 رسائل مرضى تخسرها كل ليلة",
    },
    "real_estate": {
        "en": "buyer inquiries that arrive after office hours",
        "ar": "استفسارات المشترين التي تصل بعد ساعات العمل",
        "magnet": "3 Property Inquiries You Missed This Week",
        "magnet_ar": "3 استفسارات عقارية فوّتها هذا الأسبوع",
    },
    "restaurants": {
        "en": "bookings that arrive while your team is busy",
        "ar": "الحجوزات التي تصل أثناء انشغال الفريق",
        "magnet": "5 Restaurant Bookings You Lost Last Night",
        "magnet_ar": "5 حجوزات خسرها مطعمك الليلة الماضية",
    },
    "salons": {
        "en": "appointment requests that wait hours for a reply",
        "ar": "طلبات المواعيد التي تنتظر ساعات للرد",
        "magnet": "5 Salon Bookings You Lost This Week",
        "magnet_ar": "5 مواعيد خسرها صالونك هذا الأسبوع",
    },
    "lawyers": {
        "en": "new client inquiries that arrive after hours",
        "ar": "استفسارات العملاء الجدد التي تصل بعد الدوام",
        "magnet": "Why Clients Choose the Firm That Answers First",
        "magnet_ar": "لماذا يختار العملاء المكتب الذي يرد أولاً",
    },
}

_PRIMARY, _SECONDARY, _FOOTER = "#667eea", "#764ba2", "#2d3748"
_TEXT = "#2d3748"

_CONTENT = {
    # ──────────────── CLINICS ────────────────
    ("clinics", "en", "day0"): (
        "5 patient messages you lose every night",
        "Hi {contact_name}, quick question about {company_name}.",
        "Between 9pm and 7am, how many WhatsApp messages do your "
        "patients send that no one answers? Most clinics lose 3-7 "
        "bookings every night from this. I put together a short "
        "guide: '{magnet_title}'. Grab it here: {magnet_url}. "
        "Or test our AI employee live: {alpha_url}",
        "Reply \"YES\" and I'll send both directly to your inbox.",
    ),
    ("clinics", "en", "day1"): (
        "One small fix for {company_name}",
        "Hi {contact_name},",
        "I wanted to share something small: the average patient waits "
        "6 hours for a WhatsApp reply from a clinic. The first clinic "
        "that answers usually wins the booking. That's it — just "
        "a thought. If it's useful, the full breakdown is here: "
        "{magnet_url}",
        "No pitch, no meeting. Just sharing.",
    ),
    ("clinics", "en", "day3"): (
        "How Aafiyah Care does it",
        "Hi {contact_name},",
        "Aafiyah Care Clinic used to miss 4-5 patient bookings per "
        "night. After setting up an AI employee on WhatsApp, they "
        "recover 90% of them. Same team. Same hours. Just an auto-"
        "reply that books the patient. Curious? {alpha_url}",
        "Reply \"DEMO\" and I'll show you how it works.",
    ),
    ("clinics", "en", "day7"): (
        "Closing this for {company_name}",
        "Hi {contact_name},",
        "I'm offering 3 free setups this month for clinics in Dubai. "
        "After those 3, setup costs 2,500 AED. If {company_name} "
        "wants one of the 3 free slots, reply \"SLOT\" today.",
        "Reply \"SLOT\" to claim a free setup.",
    ),
    ("clinics", "en", "day14"): (
        "Closing the file on {company_name}",
        "Hi {contact_name},",
        "I'll make this my last email so I don't clutter your inbox. "
        "If improving patient response time ever becomes a priority, "
        "you can reach me at {sender_email} or {sender_phone}. "
        "The magnet is still here: {magnet_url}",
        "No reply needed. Wishing you a great quarter.",
    ),
    ("clinics", "ar", "day0"): (
        "5 رسائل مرضى تخسرها كل ليلة",
        "مرحباً {contact_name}، سؤال سريع عن {company_name}.",
        "بين 9 مساءً و7 صباحاً، كم رسالة واتساب يرسلها مرضاك دون "
        "رد؟ معظم العيادات تخسر 3-7 حجوزات كل ليلة بسبب هذا. "
        "أعددت دليلاً قصيراً: '{magnet_title}'. حمّله من هنا: "
        "{magnet_url}. أو جرّب ALPHA مباشرة: {alpha_url}",
        "رد بكلمة \"نعم\" وسأرسل لك الاثنين مباشرة.",
    ),
    ("clinics", "ar", "day1"): (
        "فكرة صغيرة لـ {company_name}",
        "مرحباً {contact_name}،",
        "أردت مشاركة ملاحظة صغيرة: المريض العادي ينتظر 6 ساعات "
        "للرد على واتساب العيادة. أول عيادة ترد تكسب الحجز عادةً. "
        "هذا كل شيء — مجرد فكرة. إن كانت مفيدة، التفاصيل الكاملة "
        "هنا: {magnet_url}",
        "بدون عرض، بدون اجتماع. مجرد مشاركة.",
    ),
    ("clinics", "ar", "day3"): (
        "كيف تفعلها Aafiyah Care",
        "مرحباً {contact_name}،",
        "كانت عيادة Aafiyah تخسر 4-5 حجوزات كل ليلة. بعد تفعيل "
        "موظف AI على واتساب، استعادوا 90% منها. نفس الفريق، نفس "
        "الساعات. فقط رد تلقائي يحجز المريض. مهتم؟ {alpha_url}",
        "رد بكلمة \"عرض\" وسأشرح لك كيف يعمل.",
    ),
    ("clinics", "ar", "day7"): (
        "أغلق هذا لـ {company_name}",
        "مرحباً {contact_name}،",
        "أعرض 3 تفعيلات مجانية هذا الشهر لعيادات في دبي. بعد "
        "الثلاثة، التفعيل يكلف 2,500 درهم. إن أرادت {company_name} "
        "أحد الثلاثة، رد بكلمة \"فرصة\" اليوم.",
        "رد \"فرصة\" لحجز تفعيل مجاني.",
    ),
    ("clinics", "ar", "day14"): (
        "إغلاق الملف مع {company_name}",
        "مرحباً {contact_name}،",
        "هذه آخر رسالة مني حتى لا أزدحم على بريدك. إذا أصبح تحسين "
        "الرد على المرضى أولوية، يمكنك التواصل على {sender_email} "
        "أو {sender_phone}. الدليل لا يزال هنا: {magnet_url}",
        "لا حاجة للرد. أتمنى لك ربعاً ممتازاً.",
    ),
    # ──────────────── REAL ESTATE ────────────────
    ("real_estate", "en", "day0"): (
        "3 property inquiries you missed this week",
        "Hi {contact_name}, quick note about {company_name}.",
        "Buyers message on WhatsApp at 10pm, 11pm, midnight — while "
        "your office is closed. The first agent to reply wins the "
        "viewing. I made a short guide: '{magnet_title}'. Grab it: "
        "{magnet_url}. Or test the AI live: {alpha_url}",
        "Reply \"YES\" and I'll send both to your inbox.",
    ),
    ("real_estate", "en", "day1"): (
        "A thought for {company_name}",
        "Hi {contact_name},",
        "Most buyers contact 3-5 agencies for the same property. "
        "Whoever answers first usually gets the viewing. Not a "
        "sales pitch — just how the market works right now. Full "
        "breakdown: {magnet_url}",
        "Sharing because it might help.",
    ),
    ("real_estate", "en", "day3"): (
        "How SEVENTY TWO does it",
        "Hi {contact_name},",
        "SEVENTY TWO Real Estate was losing 40% of after-hours "
        "inquiries. After setup, they recover most of them — same "
        "agents, just a faster first reply. See it live: {alpha_url}",
        "Reply \"DEMO\" for a 2-minute walkthrough.",
    ),
    ("real_estate", "en", "day7"): (
        "3 free setups this month",
        "Hi {contact_name},",
        "I'm giving 3 free setups to real estate agencies in Dubai "
        "this month. After that, setup is 2,500 AED. If {company_name} "
        "wants one, reply \"SLOT\".",
        "Reply \"SLOT\" to claim.",
    ),
    ("real_estate", "en", "day14"): (
        "Closing the file on {company_name}",
        "Hi {contact_name},",
        "Last email from me. If fast WhatsApp responses ever matter, "
        "reach me at {sender_email} or {sender_phone}. The magnet is "
        "still here: {magnet_url}",
        "No reply needed.",
    ),
    ("real_estate", "ar", "day0"): (
        "3 استفسارات عقارية فوّتها هذا الأسبوع",
        "مرحباً {contact_name}، ملاحظة سريعة عن {company_name}.",
        "المشترون يراسلون على واتساب في 10 و11 مساءً ومنتصف الليل "
        "— بينما مكتبك مغلق. أول من يرد يكسب المعاينة. أعددت "
        "دليلاً: '{magnet_title}'. حمّله: {magnet_url}. أو جرّب "
        "النظام مباشرة: {alpha_url}",
        "رد بكلمة \"نعم\" وسأرسل الاثنين.",
    ),
    ("real_estate", "ar", "day1"): (
        "فكرة لـ {company_name}",
        "مرحباً {contact_name}،",
        "معظم المشترين يتواصلون مع 3-5 وكالات لنفس العقار. أول "
        "من يرد عادةً يحصل على المعاينة. ليست محاولة بيع — هذا "
        "حال السوق. التفاصيل: {magnet_url}",
        "أشارك لأنها قد تفيد.",
    ),
    ("real_estate", "ar", "day3"): (
        "كيف تفعلها SEVENTY TWO",
        "مرحباً {contact_name}،",
        "كانت SEVENTY TWO تخسر 40% من استفسارات ما بعد الدوام. "
        "بعد التفعيل، استعادوا معظمها — نفس الوكلاء، فقط رد أول "
        "أسرع. شاهد حياً: {alpha_url}",
        "رد بكلمة \"عرض\" لجولة دقيقتين.",
    ),
    ("real_estate", "ar", "day7"): (
        "3 تفعيلات مجانية هذا الشهر",
        "مرحباً {contact_name}،",
        "أعطي 3 تفعيلات مجانية لوكلات العقارات في دبي هذا الشهر. "
        "بعدها التفعيل 2,500 درهم. إن أرادت {company_name} واحدة، "
        "رد بكلمة \"فرصة\".",
        "رد \"فرصة\" للحجز.",
    ),
    ("real_estate", "ar", "day14"): (
        "إغلاق الملف مع {company_name}",
        "مرحباً {contact_name}،",
        "آخر رسالة مني. إذا احتجت ردود واتساب سريعة، تواصل على "
        "{sender_email} أو {sender_phone}. الدليل هنا: {magnet_url}",
        "لا حاجة للرد.",
    ),
    # ──────────────── RESTAURANTS ────────────────
    ("restaurants", "en", "day0"): (
        "5 bookings you lost last night",
        "Hi {contact_name}, quick note about {company_name}.",
        "Between 10pm and 11am, how many WhatsApp reservations does "
        "{company_name} lose? Most restaurants lose 3-7 nightly from "
        "unanswered messages. I made a short guide: '{magnet_title}'. "
        "Grab it: {magnet_url}. Or test live: {alpha_url}",
        "Reply \"YES\" and I'll send both.",
    ),
    ("restaurants", "en", "day1"): (
        "One small thing for {company_name}",
        "Hi {contact_name},",
        "Restaurant guests usually pick the first place that confirms "
        "the booking. If you're closed when they ask, you often lose "
        "them. Full breakdown: {magnet_url}",
        "Just sharing.",
    ),
    ("restaurants", "en", "day3"): (
        "How Fly Burgers does it",
        "Hi {contact_name},",
        "Fly Burgers was missing 6-8 bookings per week from WhatsApp. "
        "After setup, they recover most of them without adding staff. "
        "See it live: {alpha_url}",
        "Reply \"DEMO\" for a 2-minute demo.",
    ),
    ("restaurants", "en", "day7"): (
        "3 free setups this month",
        "Hi {contact_name},",
        "3 free setups for restaurants in Dubai this month. After "
        "that, 2,500 AED setup. If {company_name} wants one, "
        "reply \"SLOT\".",
        "Reply \"SLOT\".",
    ),
    ("restaurants", "en", "day14"): (
        "Closing the file on {company_name}",
        "Hi {contact_name},",
        "Last email. If fast WhatsApp replies ever matter, reach me "
        "at {sender_email} or {sender_phone}. The guide is here: "
        "{magnet_url}",
        "No reply needed.",
    ),
    ("restaurants", "ar", "day0"): (
        "5 حجوزات خسرها مطعمك الليلة",
        "مرحباً {contact_name}، ملاحظة عن {company_name}.",
        "بين 10 مساءً و11 صباحاً، كم حجز واتساب يخسره {company_name}؟ "
        "معظم المطاعم تخسر 3-7 كل ليلة من رسائل بدون رد. أعددت "
        "دليلاً: '{magnet_title}'. حمّله: {magnet_url}. أو جرّب "
        "حياً: {alpha_url}",
        "رد بكلمة \"نعم\".",
    ),
    ("restaurants", "ar", "day1"): (
        "فكرة صغيرة لـ {company_name}",
        "مرحباً {contact_name}،",
        "ضيوف المطعم عادةً يختارون أول من يؤكد الحجز. إذا كنت "
        "مغلقاً حين يسألون، تخسرهم. التفاصيل: {magnet_url}",
        "مجرد مشاركة.",
    ),
    ("restaurants", "ar", "day3"): (
        "كيف يفعلها Fly Burgers",
        "مرحباً {contact_name}،",
        "كان Fly Burgers يخسر 6-8 حجوزات أسبوعياً من واتساب. بعد "
        "التفعيل، استعادوا معظمها بدون إضافة موظفين. شاهد حياً: "
        "{alpha_url}",
        "رد \"عرض\" لجولة دقيقتين.",
    ),
    ("restaurants", "ar", "day7"): (
        "3 تفعيلات مجانية هذا الشهر",
        "مرحباً {contact_name}،",
        "3 تفعيلات مجانية لمطاعم دبي هذا الشهر. بعدها التفعيل "
        "2,500 درهم. إن أراد {company_name} واحداً، رد \"فرصة\".",
        "رد \"فرصة\".",
    ),
    ("restaurants", "ar", "day14"): (
        "إغلاق الملف مع {company_name}",
        "مرحباً {contact_name}،",
        "آخر رسالة. إذا احتجت ردود واتساب سريعة، تواصل: "
        "{sender_email} أو {sender_phone}. الدليل: {magnet_url}",
        "لا حاجة للرد.",
    ),
    # ──────────────── SALONS ────────────────
    ("salons", "en", "day0"): (
        "5 bookings you lost this week",
        "Hi {contact_name}, note about {company_name}.",
        "Appointment requests on Instagram and WhatsApp wait hours "
        "for a reply. By then, clients book with another salon. I "
        "wrote a short guide: '{magnet_title}'. Grab it: "
        "{magnet_url}. Or test live: {alpha_url}",
        "Reply \"YES\".",
    ),
    ("salons", "en", "day1"): (
        "A small idea for {company_name}",
        "Hi {contact_name},",
        "An instant WhatsApp reply that confirms the slot the moment "
        "the client asks — that's the whole idea. Your team checks "
        "confirmed bookings whenever free. Full breakdown: "
        "{magnet_url}",
        "Just sharing.",
    ),
    ("salons", "en", "day3"): (
        "How Sweet Violet does it",
        "Hi {contact_name},",
        "Sweet Violet Beauty Salon was losing 40% of Instagram "
        "appointment requests. After setup, they book most of them "
        "automatically. See it live: {alpha_url}",
        "Reply \"DEMO\".",
    ),
    ("salons", "en", "day7"): (
        "3 free setups this month",
        "Hi {contact_name},",
        "3 free setups for salons in Dubai this month. After that, "
        "2,500 AED. If {company_name} wants one, reply \"SLOT\".",
        "Reply \"SLOT\".",
    ),
    ("salons", "en", "day14"): (
        "Closing the file on {company_name}",
        "Hi {contact_name},",
        "Last email. Reach me at {sender_email} or {sender_phone} "
        "anytime. Magnet: {magnet_url}",
        "No reply needed.",
    ),
    ("salons", "ar", "day0"): (
        "5 مواعيد خسرها صالونك هذا الأسبوع",
        "مرحباً {contact_name}، ملاحظة عن {company_name}.",
        "طلبات المواعيد عبر إنستغرام وواتساب تنتظر ساعات للرد. حينها "
        "تحجز العميلة في صالون آخر. دليل قصير: '{magnet_title}'. "
        "حمّله: {magnet_url}. أو جرّب حياً: {alpha_url}",
        "رد \"نعم\".",
    ),
    ("salons", "ar", "day1"): (
        "فكرة صغيرة لـ {company_name}",
        "مرحباً {contact_name}،",
        "رد واتساب فوري يؤكد الموعد لحظة الطلب — هذه الفكرة كلها. "
        "فريقك يراجع الحجوزات المؤكدة متى توفر. التفاصيل: "
        "{magnet_url}",
        "مجرد مشاركة.",
    ),
    ("salons", "ar", "day3"): (
        "كيف تفعلها Sweet Violet",
        "مرحباً {contact_name}،",
        "كان Sweet Violet يفقد 40% من طلبات إنستغرام. بعد التفعيل، "
        "يحجزون معظمها تلقائياً. شاهد حياً: {alpha_url}",
        "رد \"عرض\".",
    ),
    ("salons", "ar", "day7"): (
        "3 تفعيلات مجانية هذا الشهر",
        "مرحباً {contact_name}،",
        "3 تفعيلات مجانية لصالونات دبي هذا الشهر. بعدها 2,500 "
        "درهم. إن أراد {company_name} واحداً: رد \"فرصة\".",
        "رد \"فرصة\".",
    ),
    ("salons", "ar", "day14"): (
        "إغلاق الملف مع {company_name}",
        "مرحباً {contact_name}،",
        "آخر رسالة. تواصل: {sender_email} أو {sender_phone}. "
        "الدليل: {magnet_url}",
        "لا حاجة للرد.",
    ),
    # ──────────────── LAWYERS ────────────────
    ("lawyers", "en", "day0"): (
        "Why clients pick the firm that answers first",
        "Hi {contact_name}, note for {company_name}.",
        "New client inquiries arrive at 10pm and on weekends. Firms "
        "that reply first win the case 60% of the time. I wrote a "
        "short breakdown: '{magnet_title}'. Grab it: {magnet_url}. "
        "Or test live: {alpha_url}",
        "Reply \"YES\".",
    ),
    ("lawyers", "en", "day1"): (
        "A thought for {company_name}",
        "Hi {contact_name},",
        "New clients usually contact 2-3 firms. Most choose the one "
        "that responds first and clearly. It's not about advertising "
        "— it's about who picks up first. Breakdown: {magnet_url}",
        "Just sharing.",
    ),
    ("lawyers", "en", "day3"): (
        "How STA Law Firm does it",
        "Hi {contact_name},",
        "STA Law Firm was losing after-hours inquiries to faster "
        "competitors. After setup, they capture most of them — "
        "without giving legal advice, just structured intake. See "
        "it live: {alpha_url}",
        "Reply \"DEMO\".",
    ),
    ("lawyers", "en", "day7"): (
        "3 free setups this month",
        "Hi {contact_name},",
        "3 free setups for law firms in Dubai this month. Then "
        "2,500 AED setup. If {company_name} wants one, "
        "reply \"SLOT\".",
        "Reply \"SLOT\".",
    ),
    ("lawyers", "en", "day14"): (
        "Closing the file on {company_name}",
        "Hi {contact_name},",
        "Last email. Reach me at {sender_email} or {sender_phone}. "
        "Magnet: {magnet_url}",
        "No reply needed.",
    ),
    ("lawyers", "ar", "day0"): (
        "لماذا يختار العملاء المكتب الذي يرد أولاً",
        "مرحباً {contact_name}، ملاحظة لـ {company_name}.",
        "استفسارات العملاء الجدد تصل في 10 مساءً وعطلة الأسبوع. "
        "المكاتب التي ترد أولاً تكسب القضية 60% من الوقت. "
        "تحليل قصير: '{magnet_title}'. حمّله: {magnet_url}. "
        "أو جرّب حياً: {alpha_url}",
        "رد \"نعم\".",
    ),
    ("lawyers", "ar", "day1"): (
        "فكرة لـ {company_name}",
        "مرحباً {contact_name}،",
        "العملاء الجدد يتواصلون مع 2-3 مكاتب عادةً. معظمهم يختار "
        "من يرد أولاً وبوضوح. ليست مسألة إعلان — بل من يرد أولاً. "
        "التفاصيل: {magnet_url}",
        "مجرد مشاركة.",
    ),
    ("lawyers", "ar", "day3"): (
        "كيف تفعلها STA Law Firm",
        "مرحباً {contact_name}،",
        "كان STA Law Firm يخسر استفسارات ما بعد الدوام لمنافسين "
        "أسرع. بعد التفعيل، يستقبل معظمها — دون تقديم استشارة "
        "قانونية، مجرد استقبال منظّم. شاهد حياً: {alpha_url}",
        "رد \"عرض\".",
    ),
    ("lawyers", "ar", "day7"): (
        "3 تفعيلات مجانية هذا الشهر",
        "مرحباً {contact_name}،",
        "3 تفعيلات مجانية لمكاتب المحاماة في دبي هذا الشهر. بعدها "
        "2,500 درهم. إن أراد {company_name} واحداً: رد \"فرصة\".",
        "رد \"فرصة\".",
    ),
    ("lawyers", "ar", "day14"): (
        "إغلاق الملف مع {company_name}",
        "مرحباً {contact_name}،",
        "آخر رسالة. تواصل: {sender_email} أو {sender_phone}. "
        "الدليل: {magnet_url}",
        "لا حاجة للرد.",
    ),
}

_GREETING = {"en": "Hi {contact_name},", "ar": "مرحباً {contact_name}،"}
_SIGNOFF = {"en": "Best regards,", "ar": "مع التحية،"}


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


def _html(lang, p1, p2, cta) -> str:
    direction = "rtl" if lang == "ar" else "ltr"
    align = "right" if lang == "ar" else "left"
    font = ("Tahoma, Arial, sans-serif" if lang == "ar"
            else "Arial, Helvetica, sans-serif")

    def para(text, extra=""):
        return ('<p style="margin:0 0 14px;font-size:15px;line-height:1.7;'
                'color:%s;%s">%s</p>'
                % (_TEXT, extra, html.escape(text)))

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
        para(p1),
        para(p2),
        para(cta, 'font-weight:bold;margin-top:18px;margin-bottom:12px;'),
        para("%s\n{sender_name}\n{sender_title}\n{sender_email} | "
              "{sender_phone}" % _SIGNOFF[lang]),
        '</td></tr>',
        '<tr><td style="background:%s;padding:18px 22px;color:#cbd5e0;'
        'font-size:12px;line-height:1.7;text-align:%s;">'
        '{unsubscribe_line}<br>{physical_address}</td></tr>'
        % (_FOOTER, align),
        '</table></td></tr></table></body></html>',
    ])


def _build() -> dict:
    out = {}
    for sector in INDUSTRY:
        out[sector] = {}
        for lang in LANGUAGES:
            out[sector][lang] = []
            for cat in CATEGORIES:
                day = DAY_OF[cat]
                subject, p1, p2, cta = _CONTENT[(sector, lang, day)]
                out[sector][lang].append({
                    "id": "%s_%s_%s" % (sector, lang, day),
                    "sector": sector, "language": lang, "category": cat,
                    "day": day, "subject": subject,
                    "body": _plain(lang, p1, p2, cta),
                    "body_html": _html(lang, p1, p2, cta)})
    return out


TEMPLATES = _build()


def get_templates(sector: str, language: str) -> list:
    return [dict(t) for t in TEMPLATES[sector][language]]


def get_template_by_id(template_id: str):
    for langs in TEMPLATES.values():
        for items in langs.values():
            for t in items:
                if t["id"] == template_id:
                    return dict(t)
    return None


def get_sequence(sector: str, language: str) -> list:
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(get_templates(sector, language),
                  key=lambda t: order[t["category"]])


def list_all_template_ids() -> list:
    return [t["id"] for langs in TEMPLATES.values()
            for items in langs.values() for t in items]


def count_by_sector() -> dict:
    return {s: sum(len(items) for items in langs.values())
            for s, langs in TEMPLATES.items()}


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
           lead_magnet_base=LEAD_MAGNET_BASE,
           calendly_link=CALENDLY_LINK,
           unsubscribe_url="") -> dict:
    t = template or {}
    p = prospect if isinstance(prospect, dict) else {}
    lang = t.get("language") or "en"
    sector = t.get("sector") or p.get("sector") or "clinics"
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

    pain = SECTOR_PAIN.get(sector, SECTOR_PAIN["clinics"])
    magnet_title = pain["magnet_ar" if lang == "ar" else "magnet"]
    magnet_url = "%s/%s" % (lead_magnet_base.rstrip("/"), sector)

    # UTM Tracking
    template_id = t.get("id", "unknown")
    utm_suffix = f"?utm_source=email&utm_medium=outreach&utm_campaign={template_id}"
    tracked_alpha_url = alpha_url + utm_suffix
    tracked_magnet_url = magnet_url + utm_suffix

    values = {
        "company_name": company,
        "contact_name": contact,
        "sector_pain": pain.get(lang, pain["en"]),
        "industry": INDUSTRY.get(sector, {}).get(lang, ""),
        "magnet_title": magnet_title,
        "magnet_url": tracked_magnet_url,
        "alpha_url": tracked_alpha_url,
        "calendly_link": _clean(calendly_link) or CALENDLY_LINK,
        "sender_name": _clean(sender_name) or SENDER_NAME,
        "sender_title": _clean(sender_title) or SENDER_TITLE,
        "sender_email": _clean(sender_email) or SENDER_EMAIL,
        "sender_phone": _clean(sender_phone) or SENDER_PHONE,
        "physical_address": _clean(physical_address) or PHYSICAL_ADDRESS,
        "unsubscribe_line": unsubscribe_line(lang, unsubscribe_url),
    }
    plain = _Fill(values)
    esc = _Fill({k: html.escape(v) for k, v in values.items()})
    return {
        "subject": str(t.get("subject", "")).format_map(plain),
        "body": str(t.get("body", "")).format_map(plain),
        "body_html": str(t.get("body_html", "")).format_map(esc),
        "unsubscribe_line": values["unsubscribe_line"],
    }


def word_count(text) -> int:
    return len(re.findall(r"\S+", text or ""))