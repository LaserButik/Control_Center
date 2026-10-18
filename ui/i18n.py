# -*- coding: utf-8 -*-
"""Internationalisation: Arabic and English translations, language
toggle, and RTL support.

t(key) returns the translated string for the current language.
get_lang() / set_lang() manage the active language via session_state
and data/settings.json.  is_rtl() returns True when the language is ar.
"""

from __future__ import annotations

TRANSLATIONS = {
    "en": {
        # navigation
        "nav.home": "Home",
        "nav.find_prospects": "Find Prospects",
        "nav.import_csv": "Import CSV",
        "nav.review_queue": "Review Queue",
        "nav.send": "Send",
        "nav.email": "Email",
        "nav.whatsapp": "WhatsApp",
        "nav.reports": "Reports",
        "nav.scheduler": "Scheduler",
        "nav.daily_automation": "Daily Automation",
        "nav.settings": "Settings",
        "nav.web_bot": "Web Bot",
        "nav.replies": "Replies",
        "nav.prospects": "Prospects",
        "nav.atlas_services": "ATLAS Services",
        "nav.reputation": "Reputation",
        "nav.backlinks": "Backlinks",
        "nav.competitive": "Competitive",
        "nav.ab_testing": "A/B Testing",
        "nav.pdf_reports": "PDF Reports",
        "nav.distribution": "Distribution",
        "nav.enrichment": "Enrichment",
        "nav.outreach_reports": "Outreach Reports",
        "nav.scrape_url": "Scrape URL",
        "nav.discovery": "Discovery",
        "nav.verify": "Verify",
        # nav sections
        "nav.section.overview": "Overview",
        "nav.section.pipeline": "Pipeline",
        "nav.section.atlas": "ATLAS",
        "nav.section.system": "System",
        # home
        "home.title": "Control Center",
        "home.subtitle": "A single pane for outreach, ATLAS, and the bot.",
        "home.activity": "Activity",
        "home.chart_runs": "Outreach runs per day",
        "home.chart_runs_sub": "Daily scheduled outreach runs over the last 30 days.",
        "home.chart_tiers": "Tier distribution",
        "home.chart_tiers_sub": "Queued prospects by quality tier, across all outreach runs.",
        "home.no_tier_data": "No tier data yet",
        "home.tier_total": "total",
        "home.delta_attempts": "{n} attempts",
        "home.delta_not_collected": "not collected yet",
        "home.delta_to_review": "{n} to review",
        "home.delta_checked": "of {n} checked",
        "home.delta_failed": "{n} failed",
        "home.prospects_sent": "Prospects sent today",
        "home.replies_week": "Replies this week",
        "home.emails_week": "Emails sent this week",
        "home.whatsapp_week": "WhatsApp sent this week",
        "home.next_actions": "What to do next",
        "home.followups_due": "You have {n} prospects due for follow-up",
        "home.no_followups": "No follow-ups due right now",
        "home.smtp_ready": "SMTP is ready",
        "home.smtp_missing": "SMTP not configured",
        "home.no_replies": "No replies today — check back in 24h",
        "home.has_replies": "You have {n} replies to review",
        "home.quick_actions": "Quick actions",
        "home.btn_find": "Find new prospects",
        "home.btn_send": "Send day 0",
        "home.btn_review": "Review queue",
        "home.btn_replies": "View replies",
        "home.advanced": "Advanced metrics",
        "home.outreach_runs": "Outreach runs",
        "home.messages_queued": "Messages queued",
        "home.messages_sent": "Messages sent",
        "home.replies_total": "Replies",
        "home.discovery_candidates": "Discovery candidates",
        "home.directories_ready": "Directories ready",
        "home.bot_sessions": "Bot sessions",
        "home.bot_success_rate": "Bot success rate",
        "home.bot_failed": "Bot failed",
        # email page
        "email.title": "Email",
        "email.subtitle": "Compose, follow up and review email outreach.",
        "email.tab_templates": "Templates",
        "email.tab_compose": "Compose",
        "email.tab_followups": "Follow-ups",
        "email.tab_history": "History",
        "email.select_file": "Select prospects file",
        "email.send_day0": "Send Day 0 Emails",
        "email.ready_status": "Ready to send {n} emails · {remaining} remaining today",
        "email.confirm_send": "I confirm: send real emails now",
        "email.dry_run": "Dry run (nothing sent)",
        "email.real_send": "Real send",
        "email.due_today": "Prospects due today",
        "email.send_followups": "Send Follow-ups",
        "email.no_followups": "No follow-ups due today",
        "email.last_sends": "Last 30 sends",
        "email.suppression": "Suppression list",
        "email.record_event": "Record event",
        "email.smtp_not_configured": "SMTP not configured",
        # settings
        "settings.title": "Settings",
        "settings.subtitle": "Language, sending limits and environment.",
        "settings.language": "Language",
        "settings.sending": "Sending",
        "settings.sender_identity": "Sender Identity",
        "settings.environment": "Environment",
        "settings.system": "System",
        "settings.daily_email_limit": "Daily email limit",
        "settings.daily_whatsapp_limit": "Daily WhatsApp limit",
        "settings.sender_name": "Sender name",
        "settings.sender_title": "Sender title",
        "settings.physical_address": "Physical address",
        "settings.env_configured": "{name} is configured",
        "settings.env_missing": "{name} not configured — add to .env",
        "settings.show_template": "Show exact .env template",
        "settings.open_folder": "Control Center folder",
        "settings.backup": "Backup settings",
        "settings.reset": "Reset to defaults",
        "settings.reset_confirm": "Are you sure? This resets all settings to defaults.",
        "settings.saved": "Settings saved.",
        "settings.follow_up_days": "Follow-up days",
        "settings.limits_caption": "The email and WhatsApp senders use these limits on every send, including the daily scheduled run. Maximum {email} emails and {wa} WhatsApp messages a day, to protect a new sending domain and number.",
        # web bot
        "webbot.title": "Web Bot Control",
        "webbot.targets": "Targets",
        "webbot.url_list": "URLs (one per line)",
        "webbot.visits_per_url": "Visits per URL",
        "webbot.randomize": "Randomize order",
        "webbot.preview": "Preview",
        "webbot.start": "Start bot",
        "webbot.stop": "Stop bot",
        "webbot.status": "Status",
        "webbot.running": "Running",
        "webbot.stopped": "Stopped",
        # common
        "common.refresh": "Refresh",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.confirm": "Confirm",
        "common.close": "Close",
        "common.download": "Download",
        "common.upload": "Upload",
        "common.search": "Search",
        "common.loading": "Loading...",
        "common.no_data": "No data available",
        "common.ok": "OK",
        "common.missing": "MISSING",
        "common.configured": "Configured",
        "common.not_configured": "Not configured",
    },
    "ar": {
        # navigation
        "nav.home": "الرئيسية",
        "nav.find_prospects": "بحث عملاء",
        "nav.import_csv": "استيراد CSV",
        "nav.review_queue": "مراجعة الطابور",
        "nav.send": "إرسال",
        "nav.email": "بريد إلكتروني",
        "nav.whatsapp": "واتساب",
        "nav.reports": "التقارير",
        "nav.scheduler": "المُجدوِل",
        "nav.daily_automation": "الأتمتة اليومية",
        "nav.settings": "الإعدادات",
        "nav.web_bot": "بوت الويب",
        "nav.replies": "الردود",
        "nav.prospects": "العملاء المحتملين",
        "nav.atlas_services": "خدمات ATLAS",
        "nav.reputation": "السمعة",
        "nav.backlinks": "الروابط الخلفية",
        "nav.competitive": "التحليل التنافسي",
        "nav.ab_testing": "اختبار A/B",
        "nav.pdf_reports": "تقارير PDF",
        "nav.distribution": "التوزيع",
        "nav.enrichment": "الإثراء",
        "nav.outreach_reports": "تقارير التواصل",
        "nav.scrape_url": "استخراج URL",
        "nav.discovery": "الاكتشاف",
        "nav.verify": "التحقق",
        # nav sections
        "nav.section.overview": "نظرة عامة",
        "nav.section.pipeline": "المسار",
        "nav.section.atlas": "ATLAS",
        "nav.section.system": "النظام",
        # home
        "home.title": "لوحة التحكم",
        "home.subtitle": "لوحة واحدة للتواصل وATLAS والبوت.",
        "home.activity": "النشاط",
        "home.chart_runs": "جولات التواصل يومياً",
        "home.chart_runs_sub": "جولات التواصل المجدولة يومياً خلال آخر 30 يوماً.",
        "home.chart_tiers": "توزيع الفئات",
        "home.chart_tiers_sub": "العملاء في الطابور حسب فئة الجودة عبر جميع جولات التواصل.",
        "home.no_tier_data": "لا توجد بيانات فئات بعد",
        "home.tier_total": "الإجمالي",
        "home.delta_attempts": "{n} محاولة",
        "home.delta_not_collected": "لم تُجمع بعد",
        "home.delta_to_review": "{n} للمراجعة",
        "home.delta_checked": "من {n} تم فحصها",
        "home.delta_failed": "{n} فشلت",
        "home.prospects_sent": "عملاء أرسلوا اليوم",
        "home.replies_week": "ردود هذا الأسبوع",
        "home.emails_week": "بريد مرسل هذا الأسبوع",
        "home.whatsapp_week": "واتساب هذا الأسبوع",
        "home.next_actions": "الخطوات التالية",
        "home.followups_due": "لديك {n} عملاء بحاجة لمتابعة",
        "home.no_followups": "لا توجد متابعات مستحقة الآن",
        "home.smtp_ready": "SMTP جاهز",
        "home.smtp_missing": "SMTP غير مهيأ",
        "home.no_replies": "لا ردود اليوم — تحقق بعد 24 ساعة",
        "home.has_replies": "لديك {n} ردود للمراجعة",
        "home.quick_actions": "إجراءات سريعة",
        "home.btn_find": "بحث عن عملاء جدد",
        "home.btn_send": "إرسال اليوم 0",
        "home.btn_review": "مراجعة الطابور",
        "home.btn_replies": "عرض الردود",
        "home.advanced": "مقاييس متقدمة",
        "home.outreach_runs": "جولات التواصل",
        "home.messages_queued": "رسائل في الانتظار",
        "home.messages_sent": "رسائل مرسلة",
        "home.replies_total": "الردود",
        "home.discovery_candidates": "مرشحين للاكتشاف",
        "home.directories_ready": "أدلة جاهزة",
        "home.bot_sessions": "جلسات البوت",
        "home.bot_success_rate": "نسبة نجاح البوت",
        "home.bot_failed": "فشل البوت",
        # email page
        "email.title": "البريد الإلكتروني",
        "email.subtitle": "إنشاء ومتابعة ومراجعة رسائل التواصل.",
        "email.tab_templates": "القوالب",
        "email.tab_compose": "إنشاء",
        "email.tab_followups": "المتابعات",
        "email.tab_history": "السجل",
        "email.select_file": "اختر ملف العملاء",
        "email.send_day0": "إرسال رسائل اليوم 0",
        "email.ready_status": "جاهز لإرسال {n} بريد · متبقي {remaining} اليوم",
        "email.confirm_send": "أؤكد: إرسال بريد حقيقي الآن",
        "email.dry_run": "تجربة (بدون إرسال)",
        "email.real_send": "إرسال حقيقي",
        "email.due_today": "عملاء مستحقين اليوم",
        "email.send_followups": "إرسال المتابعات",
        "email.no_followups": "لا متابعات مستحقة اليوم",
        "email.last_sends": "آخر 30 إرسال",
        "email.suppression": "قائمة الحظر",
        "email.record_event": "تسجيل حدث",
        "email.smtp_not_configured": "SMTP غير مهيأ",
        # settings
        "settings.title": "الإعدادات",
        "settings.subtitle": "اللغة وحدود الإرسال والبيئة.",
        "settings.language": "اللغة",
        "settings.sending": "الإرسال",
        "settings.sender_identity": "هوية المرسل",
        "settings.environment": "البيئة",
        "settings.system": "النظام",
        "settings.daily_email_limit": "حد البريد اليومي",
        "settings.daily_whatsapp_limit": "حد الواتساب اليومي",
        "settings.sender_name": "اسم المرسل",
        "settings.sender_title": "لقب المرسل",
        "settings.physical_address": "العنوان الفعلي",
        "settings.env_configured": "{name} مهيأ",
        "settings.env_missing": "{name} غير مهيأ — أضفه إلى .env",
        "settings.show_template": "عرض قالب .env",
        "settings.open_folder": "مجلد لوحة التحكم",
        "settings.backup": "نسخ احتياطي للإعدادات",
        "settings.reset": "إعادة الضبط",
        "settings.reset_confirm": "هل أنت متأكد؟ سيعيد هذا جميع الإعدادات إلى الافتراضي.",
        "settings.saved": "تم الحفظ.",
        "settings.follow_up_days": "أيام المتابعة",
        "settings.limits_caption": "يستخدم مُرسلا البريد والواتساب هذه الحدود في كل إرسال، بما في ذلك التشغيل اليومي المجدول. الحد الأقصى {email} رسالة بريد و{wa} رسالة واتساب يومياً لحماية نطاق الإرسال والرقم الجديدين.",
        # web bot
        "webbot.title": "بوت الويب",
        "webbot.targets": "الأهداف",
        "webbot.url_list": "روابط (واحد لكل سطر)",
        "webbot.visits_per_url": "زيارات لكل رابط",
        "webbot.randomize": "ترتيب عشوائي",
        "webbot.preview": "معاينة",
        "webbot.start": "تشغيل البوت",
        "webbot.stop": "إيقاف البوت",
        "webbot.status": "الحالة",
        "webbot.running": "يعمل",
        "webbot.stopped": "متوقف",
        # common
        "common.refresh": "تحديث",
        "common.save": "حفظ",
        "common.cancel": "إلغاء",
        "common.confirm": "تأكيد",
        "common.close": "إغلاق",
        "common.download": "تنزيل",
        "common.upload": "رفع",
        "common.search": "بحث",
        "common.loading": "جاري التحميل...",
        "common.no_data": "لا توجد بيانات",
        "common.ok": "مهيأ",
        "common.missing": "غير موجود",
        "common.configured": "مهيأ",
        "common.not_configured": "غير مهيأ",
    },
}


# Page strings: (English, Arabic) side by side, merged into TRANSLATIONS
# below so both dictionaries always get every key.
_PAIRS = {
    # ATLAS Services: run-here tabs
    "services.tab_monitor": ("Website monitor", "مراقبة المواقع"),
    "services.tab_seo": ("SEO intelligence", "تحليل SEO"),
    "services.tab_health": ("Content health", "صحة المحتوى"),
    # network checks (Website Monitor, Content Health)
    "net.monitor_caption": (
        "Checks each address once and shows whether it loads and how fast. "
        "You can type example.com without https://.",
        "يفحص كل عنوان مرة واحدة ويبيّن هل يعمل وما مدى سرعته. يمكنك كتابة "
        "example.com بدون https://."),
    "net.health_caption": (
        "Crawls up to the chosen number of pages on one site, follows its "
        "robots.txt, and lists every page with its status and speed.",
        "يتصفح حتى العدد المحدد من صفحات موقع واحد مع احترام ملف robots.txt، "
        "ويعرض كل صفحة مع حالتها وسرعتها."),
    "net.urls_label": ("Websites (one per line)", "المواقع (واحد في كل سطر)"),
    "net.base_label": ("Website", "الموقع"),
    "net.max_pages": ("Max pages", "الحد الأقصى للصفحات"),
    "net.check_button": ("Check websites", "فحص المواقع"),
    "net.scan_button": ("Scan site", "فحص الموقع"),
    "net.try_example": ("Try example", "جرّب مثالاً"),
    "net.checking": ("Checking {n} website(s)…", "جارٍ فحص {n} موقع…"),
    "net.scanning": ("Scanning…", "جارٍ الفحص…"),
    "net.enter_url": ("Enter at least one website address.",
                      "أدخل عنوان موقع واحداً على الأقل."),
    "net.col_url": ("URL", "الرابط"),
    "net.col_status": ("Status", "الحالة"),
    "net.col_time": ("Time (ms)", "الوقت (مللي ثانية)"),
    "net.col_notes": ("Notes", "ملاحظات"),
    "net.level_ok": ("OK", "سليم"),
    "net.level_warn": ("Warning", "تنبيه"),
    "net.level_error": ("Error", "خطأ"),
    "net.site_up": ("Site is up", "الموقع يعمل"),
    "net.page_ok": ("OK · {n} links", "سليمة · {n} رابط"),
    "net.slow": ("Slow: took more than 3 seconds",
                 "بطيء: استغرق أكثر من 3 ثوانٍ"),
    "net.http_403": ("Access refused (HTTP {code})",
                     "الوصول مرفوض (HTTP {code})"),
    "net.http_404": ("Page not found (HTTP {code})",
                     "الصفحة غير موجودة (HTTP {code})"),
    "net.http_5xx": ("Server error (HTTP {code})",
                     "خطأ في الخادم (HTTP {code})"),
    "net.http_error": ("The site answered with an error (HTTP {code})",
                       "ردّ الموقع بخطأ (HTTP {code})"),
    "net.invalid_domain": ("Please enter a valid domain (example.com)",
                           "يرجى إدخال نطاق صحيح (example.com)"),
    "net.unsupported_scheme": (
        "Only http:// and https:// addresses can be checked",
        "يمكن فحص عناوين http:// و https:// فقط"),
    "net.connection_failed": ("Could not reach the site",
                              "تعذّر الوصول إلى الموقع"),
    "net.timeout": ("The site took too long to respond",
                    "استغرق الموقع وقتاً طويلاً للرد"),
    "net.ssl_error": ("SSL certificate error", "خطأ في شهادة SSL"),
    "net.too_many_redirects": (
        "The site keeps redirecting and never loads",
        "يعيد الموقع التوجيه باستمرار ولا يكتمل التحميل"),
    "net.robots_disallowed": ("The site's robots.txt blocks this check",
                              "ملف robots.txt في الموقع يمنع هذا الفحص"),
    "net.robots_server_error": (
        "The site's robots.txt answered with a server error (HTTP {code}), "
        "so the scan was stopped",
        "ردّ ملف robots.txt في الموقع بخطأ في الخادم (HTTP {code})، لذلك "
        "أُوقف الفحص"),
    "net.request_failed": ("The request failed", "فشل الطلب"),
    "net.requests_not_installed": ("The requests library is not installed",
                                   "مكتبة requests غير مثبتة"),
    "net.pages_scanned": ("Pages scanned", "الصفحات المفحوصة"),
    "net.broken": ("Broken", "معطلة"),
    "net.blocked": ("Blocked by robots.txt", "محظورة عبر robots.txt"),

    # shared
    "common.app_name": ("Control Center", "لوحة التحكم"),
    "common.command": ("Command", "الأمر"),
    "common.exit_code": ("Exit code {code}", "رمز الخروج {code}"),
    "common.failed": ("failed", "فشل"),
    "common.output": ("Output", "المخرجات"),
    "common.errors": ("Errors", "الأخطاء"),
    "common.nothing_yet": ("Nothing here yet", "لا يوجد شيء بعد"),
    "common.no_queue_runs": ("No runs with a queue yet.",
                             "لا توجد جولات تحتوي على طابور بعد."),
    "common.run": ("Run", "الجولة"),
    "common.status": ("Status", "الحالة"),
    "common.shown": ("Shown", "المعروض"),
    "common.export_csv": ("Export shown as CSV", "تصدير المعروض بصيغة CSV"),
    "common.chart_unavailable": ("Chart unavailable",
                                 "الرسم البياني غير متاح"),
    "common.upload_limit": ("Up to 200 MB per file",
                            "حتى 200 ميغابايت لكل ملف"),
    "common.lang_ar": ("Arabic", "العربية"),
    "common.lang_en": ("English", "الإنجليزية"),
    # status values (display only; the data keeps the English code)
    "status.pending": ("pending", "قيد الانتظار"),
    "status.approved": ("approved", "موافق عليه"),
    "status.rejected": ("rejected", "مرفوض"),
    "status.sent": ("sent", "مُرسل"),
    "status.failed": ("failed", "فشل"),
    "status.blocked": ("blocked", "محظور"),
    "status.skipped": ("skipped", "متخطى"),
    "status.dry_run": ("dry run", "تجربة"),
    # Home
    "home.tier_label": ("Tier {k}", "الفئة {k}"),

    # Scrape URL
    "scrape.page_title": ("Scrape URL", "استخراج رابط"),
    "scrape.title": ("Scrape one URL", "استخراج صفحة واحدة"),
    "scrape.subtitle": (
        "One page, robots.txt enforced, written for review. Nothing is sent.",
        "صفحة واحدة مع تطبيق robots.txt، وتُحفظ للمراجعة. لا يُرسل أي شيء."),
    "scrape.before_title": ("Before you scrape", "قبل الاستخراج"),
    "scrape.before_body": (
        "Respect <b>robots.txt</b> and the site's <b>Terms of Service</b>. "
        "The scraper fetches robots.txt first and stops if the page is "
        "disallowed, but it cannot read the Terms — that check is yours.",
        "احترم ملف <b>robots.txt</b> و<b>شروط الخدمة</b> الخاصة بالموقع. "
        "تقرأ الأداة ملف robots.txt أولاً وتتوقف إذا كانت الصفحة ممنوعة، "
        "لكنها لا تستطيع قراءة الشروط — هذا التحقق مسؤوليتك."),
    "scrape.target": ("Target", "الهدف"),
    "scrape.target_sub": (
        "Exactly one page is read; links and pagination are not followed.",
        "تُقرأ صفحة واحدة فقط؛ ولا تُتبع الروابط ولا الصفحات التالية."),
    "scrape.url_label": ("Target URL", "رابط الهدف"),
    "scrape.max_prospects": ("Max prospects", "الحد الأقصى للعملاء"),
    "scrape.max_help": ("Hard cap of 10 in the scraper itself.",
                        "حد ثابت قدره 10 داخل أداة الاستخراج نفسها."),
    "scrape.delay": ("Delay before the page (seconds)",
                     "الانتظار قبل الصفحة (ثوانٍ)"),
    "scrape.delay_help": (
        "Minimum 5 s; a longer robots.txt Crawl-delay wins.",
        "5 ثوانٍ كحد أدنى؛ وإذا حدد ملف robots.txt مهلة أطول فهي المعتمدة."),
    "scrape.ack": (
        "I confirm this site's Terms of Service allow automated access.",
        "أؤكد أن شروط خدمة هذا الموقع تسمح بالوصول الآلي."),
    "scrape.dry": ("Dry Run", "تجربة"),
    "scrape.real": ("Real Scrape", "استخراج فعلي"),
    "scrape.tick_terms": (
        "Tick the Terms confirmation to enable a real scrape",
        "ضع علامة على تأكيد الشروط لتفعيل الاستخراج الفعلي"),
    "scrape.dry_header": ("Dry run", "تجربة"),
    "scrape.dry_sub": (
        "The command a real scrape would run. Nothing was fetched.",
        "الأمر الذي سينفذه الاستخراج الفعلي. لم يُجلب أي شيء."),
    "scrape.result": ("Result", "النتيجة"),
    "scrape.scraping": (
        "Scraping one page — waiting at least {n}s first…",
        "جارٍ استخراج صفحة واحدة — الانتظار {n} ثانية على الأقل أولاً…"),

    # Import CSV
    "csv.page_title": ("Import CSV", "استيراد CSV"),
    "csv.title": ("Import a CSV", "استيراد ملف CSV"),
    "csv.caption": (
        "Runs `outreach.pipeline import`: CSV → E.164 phones → skip "
        "non-businesses and non-mobiles → score → personalise → a review "
        "queue. No network, nothing sent.",
        "يشغّل `outreach.pipeline import`: ملف CSV ← أرقام بصيغة E.164 ← "
        "تخطي غير الشركات وغير الجوالات ← التقييم ← التخصيص ← طابور "
        "للمراجعة. بدون اتصال بالإنترنت، ولا يُرسل أي شيء."),
    "csv.uploader": ("Instant Data Scraper CSV",
                     "ملف CSV من Instant Data Scraper"),
    "csv.source_url": ("Source URL (for the record)",
                       "رابط المصدر (للتوثيق)"),
    "csv.import": ("Import", "استيراد"),
    "csv.importing": ("Importing…", "جارٍ الاستيراد…"),
    "csv.done": ("Done. Open Queue Review to approve entries.",
                 "تم. افتح مراجعة الطابور للموافقة على الإدخالات."),

    # Discovery
    "disc.page_title": ("Discovery", "الاكتشاف"),
    "disc.title": ("Discovery", "الاكتشاف"),
    "disc.caption": (
        "Runs `outreach.discover_pipeline discover`. Offline uses the "
        "curated seeds only; online also runs DuckDuckGo search and homepage "
        "cross-references (robots permitting).",
        "يشغّل `outreach.discover_pipeline discover`. دون اتصال يستخدم "
        "القوائم المنتقاة فقط؛ ومع الاتصال يبحث أيضاً عبر DuckDuckGo ويقارن "
        "الصفحات الرئيسية (إذا سمح ملف robots.txt)."),
    "disc.online": ("Online (DuckDuckGo search + cross-references)",
                    "متصل (بحث DuckDuckGo + مقارنات)"),
    "disc.online_warning": (
        "This makes network requests from the outreach venv: up to ~20 "
        "searches (10s apart) and ~10 homepage reads.",
        "هذا يرسل طلبات عبر الإنترنت من بيئة outreach: حتى نحو 20 عملية "
        "بحث (بفاصل 10 ثوانٍ) ونحو 10 قراءات لصفحات رئيسية."),
    "disc.current": ("Current candidates on disk",
                     "المرشحون الحاليون المحفوظون"),
    "disc.count": ("{n} candidate(s).", "{n} مرشح."),
    "disc.col_host": ("Host", "النطاق"),
    "disc.col_country": ("Country", "الدولة"),
    "disc.col_type": ("Type", "النوع"),
    "disc.col_source": ("Source", "المصدر"),
    "disc.run": ("Run discovery", "تشغيل الاكتشاف"),
    "disc.running": ("Discovering…", "جارٍ الاكتشاف…"),

    # Verify
    "verify.page_title": ("Verify", "التحقق"),
    "verify.title": ("Verify directories", "التحقق من الأدلة"),
    "verify.caption": (
        "Runs `outreach.discover_pipeline verify --online`. For each "
        "candidate it checks robots.txt, the homepage and the first Terms "
        "page, then rates it Ready / Review / No-go. No listing is scraped.",
        "يشغّل `outreach.discover_pipeline verify --online`. لكل مرشح يفحص "
        "ملف robots.txt والصفحة الرئيسية وأول صفحة شروط، ثم يصنفه: جاهز / "
        "يحتاج مراجعة / مرفوض. لا تُستخرج أي قوائم."),
    "verify.ready": ("Ready", "جاهز"),
    "verify.review": ("Review", "يحتاج مراجعة"),
    "verify.nogo": ("No-go", "مرفوض"),
    "verify.col_url": ("URL", "الرابط"),
    "verify.col_verdict": ("Verdict", "التقييم"),
    "verify.col_reason": ("Reason", "السبب"),
    "verify.not_permission": (
        "Ready is not permission — read each site's Terms before scraping "
        "it.",
        "تصنيف «جاهز» ليس إذناً — اقرأ شروط كل موقع قبل الاستخراج منه."),
    "verify.none": (
        "No verification results yet. Run discovery first, then verify.",
        "لا توجد نتائج تحقق بعد. شغّل الاكتشاف أولاً ثم التحقق."),
    "verify.warning": (
        "Verification makes network requests (several per directory, ≥5s "
        "apart). It can take many minutes.",
        "يرسل التحقق طلبات عبر الإنترنت (عدة طلبات لكل دليل، بفاصل 5 ثوانٍ "
        "على الأقل). قد يستغرق دقائق عديدة."),
    "verify.run": ("Run verification (online)", "تشغيل التحقق (متصل)"),
    "verify.running": ("Verifying… this may take a while",
                       "جارٍ التحقق… قد يستغرق ذلك بعض الوقت"),

    # Queue Review
    "queue.page_title": ("Queue Review", "مراجعة الطابور"),
    "queue.title": ("Queue review", "مراجعة الطابور"),
    "queue.caption": (
        "Approve or reject entries with `outreach.queue_cli`. Approving "
        "approves the recipient; WhatsApp still sends the Meta-approved "
        "template, not the body shown here. Underlying files are never "
        "edited here except through the queue CLI.",
        "وافق على الإدخالات أو ارفضها عبر `outreach.queue_cli`. الموافقة "
        "تعني الموافقة على المستلم؛ ويظل واتساب يرسل القالب المعتمد من Meta، "
        "لا النص المعروض هنا. لا تُعدّل الملفات الأصلية هنا إلا عبر أداة "
        "الطابور."),
    "queue.col_queue_id": ("Queue ID", "رقم الإدخال"),
    "queue.col_status": ("Status", "الحالة"),
    "queue.col_language": ("Language", "اللغة"),
    "queue.col_tier": ("Tier", "الفئة"),
    "queue.col_company": ("Company", "الشركة"),
    "queue.col_to": ("To", "إلى"),
    "queue.col_subject": ("Subject", "الموضوع"),
    "queue.search": ("Search company or phone", "ابحث بالشركة أو الهاتف"),
    "queue.sort_by": ("Sort by", "ترتيب حسب"),
    "queue.total": ("Entries total", "إجمالي الإدخالات"),
    "queue.pending_all": ("Pending (all)", "قيد الانتظار (الكل)"),
    "queue.approved_all": ("Approved (all)", "موافق عليها (الكل)"),
    "queue.bulk": ("Bulk decide (from the filtered view)",
                   "قرار جماعي (من العرض المصفّى)"),
    "queue.no_pending": ("No pending entries in the current filter.",
                         "لا توجد إدخالات قيد الانتظار في التصفية الحالية."),
    "queue.entries": ("Queue entries", "إدخالات الطابور"),
    "queue.reviewer": ("Reviewer", "المراجِع"),
    "queue.reject_reason": ("Reject reason", "سبب الرفض"),
    "queue.reason_default": ("not a fit", "غير مناسب"),
    "queue.approve": ("Approve selected", "الموافقة على المحدد"),
    "queue.reject": ("Reject selected", "رفض المحدد"),
    "queue.approving": ("Approving {id}…", "جارٍ الموافقة على {id}…"),
    "queue.rejecting": ("Rejecting {id}…", "جارٍ رفض {id}…"),

    # Send
    "send.page_title": ("Send", "إرسال"),
    "send.title": ("Send WhatsApp", "إرسال واتساب"),
    "send.caption": (
        "Runs `outreach.pipeline send`. Only approved entries go out, and "
        "the pipeline still applies its own approved-queue gate and "
        "AE/SA-mobile checks. Dry run first.",
        "يشغّل `outreach.pipeline send`. لا تُرسل إلا الإدخالات الموافق "
        "عليها، ويطبّق المسار أيضاً بوابة الطابور المعتمد وفحص جوالات "
        "الإمارات والسعودية. ابدأ بالتجربة."),
    "send.approved": ("Approved entries in this run",
                      "الإدخالات الموافق عليها في هذه الجولة"),
    "send.template_name": ("Template name", "اسم القالب"),
    "send.template_lang": ("Template language", "لغة القالب"),
    "send.verified": ("Verified working values: {name} / {lang}",
                      "القيم المجرّبة والعاملة: {name} / {lang}"),
    "send.step_dry": ("1) Dry run", "1) تجربة"),
    "send.run_dry": ("Run dry run", "تشغيل التجربة"),
    "send.dry_running": ("Dry run — nothing is sent…",
                         "تجربة — لا يُرسل أي شيء…"),
    "send.step_real": ("2) Real send", "2) إرسال فعلي"),
    "send.warning": (
        "A real send messages people on WhatsApp through ALPHA's number. "
        "Recipients must have opted in; marketing templates are billed by "
        "Meta.",
        "الإرسال الفعلي يراسل الأشخاص عبر واتساب من رقم ALPHA. يجب أن يكون "
        "المستلمون قد وافقوا مسبقاً؛ وتحتسب Meta رسوم قوالب التسويق."),
    "send.confirm": (
        "Yes — send real WhatsApp messages for the approved entries in this "
        "run.",
        "نعم — أرسل رسائل واتساب فعلية للإدخالات الموافق عليها في هذه "
        "الجولة."),
    "send.real": ("Send for real", "إرسال فعلي"),
    "send.sending": ("Sending approved entries…",
                     "جارٍ إرسال الإدخالات الموافق عليها…"),

    # Replies
    "replies.page_title": ("Replies", "الردود"),
    "replies.title": ("WhatsApp activity", "نشاط واتساب"),
    "replies.inbound": ("Inbound replies", "الردود الواردة"),
    "replies.not_collected": (
        "Inbound replies are not collected yet (the pipeline sends only). "
        "This populates once reply handling exists.",
        "لا تُجمع الردود الواردة بعد (المسار يرسل فقط). سيمتلئ هذا القسم "
        "عند تفعيل معالجة الردود."),
    "replies.outbound": ("Outbound attempts (from the send logs)",
                         "محاولات الإرسال (من سجلات الإرسال)"),
    "replies.no_outbound": ("No outbound WhatsApp attempts logged yet.",
                            "لم تُسجل أي محاولات إرسال واتساب بعد."),
    "replies.search": ("Search (status / reason / run)",
                       "بحث (الحالة / السبب / الجولة)"),
    "replies.date_range": ("Date range", "نطاق التاريخ"),
    "replies.attempts": ("Attempts", "المحاولات"),
    "replies.sent": ("Sent", "المُرسلة"),
    "replies.hash_note": (
        "Phone numbers are stored only as a hash; nothing in clear is "
        "shown.",
        "تُحفظ أرقام الهواتف كقيم مشفّرة فقط؛ ولا يُعرض أي رقم بشكل صريح."),
    "replies.col_run_id": ("Run", "الجولة"),
    "replies.col_at": ("Time", "الوقت"),
    "replies.col_status": ("Status", "الحالة"),
    "replies.col_reason": ("Reason", "السبب"),
    "replies.col_mode": ("Mode", "الوضع"),
    "replies.col_provider_id": ("Provider ID", "معرّف المزوّد"),
    "replies.col_to_hash": ("Recipient hash", "بصمة المستلم"),

    # Prospects
    "prospects.page_title": ("Prospects", "العملاء المحتملون"),
    "prospects.title": ("Prospects", "العملاء المحتملون"),
    "prospects.no_runs": ("No runs yet.", "لا توجد جولات بعد."),
    "prospects.none_in_run": ("No prospects in this run.",
                              "لا يوجد عملاء محتملون في هذه الجولة."),
    "prospects.col_company": ("Company", "الشركة"),
    "prospects.col_phone": ("Phone", "الهاتف"),
    "prospects.col_country": ("Country", "الدولة"),
    "prospects.col_industry": ("Industry", "القطاع"),
    "prospects.col_tier": ("Tier", "الفئة"),
    "prospects.col_score": ("Score", "التقييم"),
    "prospects.col_has_mobile": ("Has mobile", "لديه جوال"),
    "prospects.col_skipped": ("Skipped", "متخطى"),
    "prospects.col_skip_reason": ("Skip reason", "سبب التخطي"),
    "prospects.industry_contains": ("Industry contains",
                                    "القطاع يحتوي على"),
    "prospects.mobile_only": ("Has mobile only", "أصحاب الجوال فقط"),
    "prospects.total": ("Prospects", "العملاء المحتملون"),
    "prospects.with_mobile": ("With mobile", "لديهم جوال"),
    "prospects.score_chart": ("Score distribution (shown)",
                              "توزيع التقييمات (المعروض)"),
}

for _key, (_en, _ar) in _PAIRS.items():
    TRANSLATIONS["en"][_key] = _en
    TRANSLATIONS["ar"][_key] = _ar


def get_lang() -> str:
    try:
        import streamlit as st
        lang = st.session_state.get("cc_language")
        if lang in ("ar", "en"):
            return lang
    except Exception:
        pass
    from ui.settings_store import load_settings
    return load_settings().get("language", "en")


def set_lang(lang: str) -> None:
    if lang not in ("ar", "en"):
        return
    try:
        import streamlit as st
        st.session_state["cc_language"] = lang
    except Exception:
        pass
    from ui.settings_store import load_settings, save_settings
    s = load_settings()
    s["language"] = lang
    save_settings(s)


def t(key: str, lang: str = "") -> str:
    if not lang:
        lang = get_lang()
    table = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return table.get(key, TRANSLATIONS["en"].get(key, key))


def is_rtl(lang: str = "") -> bool:
    if not lang:
        lang = get_lang()
    return lang == "ar"
