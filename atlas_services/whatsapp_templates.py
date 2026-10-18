# -*- coding: utf-8 -*-
"""ATLAS WhatsApp templates: 5 sectors x 2 languages x 2 steps = 20
business-initiated messages for ALPHA outreach, written for Meta review.

Steps:  day0_initial   the first message
        day2_followup  a short follow-up two days later
Plus one late nudge per language (day7), shared by all sectors, used by
the unified sequence — LATE_TEMPLATES, outside the 20.

Rules kept by every body (tests check them):
  - at most 160 characters; one variable only, {company_name}, never at
    the very start or end (Meta rejects that)
  - no emoji, no links, no phone numbers, no ALL-CAPS words
    (the product is written "Alpha" here for that reason)
  - none of: guaranteed, free, urgent, click here
  - ends with a question, to invite a reply
  - "name" is the exact template name submitted to Meta: lowercase
    letters, digits and underscores only

Nothing here talks to Meta. export_for_meta_submission() only builds the
payloads; a person submits them in Meta Business Suite.
"""

from __future__ import annotations

import re

MAX_CHARS = 160
CATEGORIES = ("day0_initial", "day2_followup")
DAY_OF = {"day0_initial": "day0", "day2_followup": "day2",
          "day7_nudge": "day7"}
LANGUAGES = ("ar", "en")
META_CATEGORY = "MARKETING"
EXAMPLE_COMPANY = "Smile Dental Clinic"

# (sector, language) -> (day0 body, day2 body)
_BODIES = {
    ("clinics", "en"): (
        "Hello {company_name}, many patients message clinics on WhatsApp "
        "after hours. Alpha, our AI assistant, replies 24/7 in Arabic and "
        "English. Open to a short demo?",
        "Hi {company_name}, a quick follow-up: a fast first reply often "
        "decides which clinic a patient books with. Would a short demo of "
        "Alpha help?"),
    ("clinics", "ar"): (
        "مرحباً فريق {company_name}، كثير من المرضى يراسلون العيادات عبر "
        "واتساب بعد الدوام. Alpha يرد على مدار الساعة بالعربية والإنجليزية. "
        "هل يناسبكم عرض قصير؟",
        "مرحباً فريق {company_name}، الرد الأول السريع غالباً ما يحدد العيادة "
        "التي يحجز فيها المريض. هل يفيدكم عرض قصير لـ Alpha؟"),
    ("real_estate", "en"): (
        "Hello {company_name}, buyer inquiries often arrive on WhatsApp "
        "after office hours. Alpha replies instantly in Arabic and English. "
        "Worth a short chat?",
        "Hi {company_name}, buyers often message several agencies at once "
        "and the first reply usually wins the viewing. Shall I send a short "
        "demo of Alpha?"),
    ("real_estate", "ar"): (
        "مرحباً فريق {company_name}، تصل استفسارات المشترين عبر واتساب غالباً "
        "بعد ساعات العمل. Alpha يرد فوراً بالعربية والإنجليزية. هل تناسبكم "
        "مكالمة قصيرة؟",
        "مرحباً فريق {company_name}، يتواصل المشتري غالباً مع عدة وكالات، "
        "والرد الأول يحسم المعاينة عادةً. هل أرسل لكم عرضاً قصيراً لـ Alpha؟"),
    ("restaurants", "en"): (
        "Hello {company_name}, guests send table requests on WhatsApp at all "
        "hours. Alpha replies instantly and takes the booking details. "
        "Interested in a quick demo?",
        "Hi {company_name}, a quick reply often decides where a guest books "
        "a table. Alpha confirms requests straight away. Want to see how it "
        "works?"),
    ("restaurants", "ar"): (
        "مرحباً فريق {company_name}، يرسل الضيوف طلبات الحجز عبر واتساب في كل "
        "الأوقات. Alpha يرد فوراً ويسجل تفاصيل الحجز. هل تودون رؤية عرض سريع؟",
        "مرحباً فريق {company_name}، الرد السريع كثيراً ما يحسم أين يحجز الضيف "
        "طاولته. Alpha يؤكد الطلب فوراً. هل تودون معرفة كيف يعمل؟"),
    ("salons", "en"): (
        "Hello {company_name}, booking requests on WhatsApp often come while "
        "your team is busy. Alpha replies instantly and offers open slots. "
        "Open to a short demo?",
        "Hi {company_name}, a simple idea: confirm each booking request the "
        "moment it arrives, so clients stop looking elsewhere. Shall I show "
        "you how?"),
    ("salons", "ar"): (
        "مرحباً فريق {company_name}، تصل طلبات الحجز عبر واتساب غالباً والفريق "
        "مشغول. Alpha يرد فوراً ويعرض المواعيد المتاحة. هل يناسبكم عرض قصير؟",
        "مرحباً فريق {company_name}، فكرة بسيطة: تأكيد كل طلب حجز لحظة وصوله "
        "حتى لا يبحث العميل في مكان آخر. هل أريكم كيف؟"),
    ("lawyers", "en"): (
        "Hello {company_name}, new client inquiries need a fast, "
        "professional first reply, even after hours. Alpha handles that on "
        "WhatsApp. Worth a short call?",
        "Hi {company_name}, people often contact more than one firm and many "
        "choose the one that answers first. Would a short demo of Alpha be "
        "useful?"),
    ("lawyers", "ar"): (
        "مرحباً فريق {company_name}، استفسارات العملاء الجدد تحتاج رداً أول "
        "سريعاً ومهنياً حتى بعد الدوام. Alpha يتولى ذلك عبر واتساب. هل تناسبكم "
        "مكالمة قصيرة؟",
        "مرحباً فريق {company_name}، يتواصل الناس غالباً مع أكثر من مكتب، "
        "وكثيرون يختارون من يرد أولاً. هل يفيدكم عرض قصير لـ Alpha؟"),
}

_LATE = {
    "en": "Hi {company_name}, checking in one last time about Alpha for "
          "your WhatsApp inquiries. Is this worth a short conversation?",
    "ar": "مرحباً فريق {company_name}، أتواصل معكم للمرة الأخيرة بخصوص Alpha "
          "للرد على استفسارات واتساب. هل يستحق الأمر حديثاً قصيراً؟",
}


def _build() -> dict:
    out = {}
    for (sector, lang), (day0, day2) in _BODIES.items():
        out.setdefault(sector, {})[lang] = [
            {"id": "wa_%s_%s_day0" % (sector, lang),
             "category": "day0_initial", "day": "day0",
             "name": "alpha_%s_%s_v1" % (sector, lang),
             "sector": sector, "language": lang, "body": day0,
             "variables": ["{company_name}"]},
            {"id": "wa_%s_%s_day2" % (sector, lang),
             "category": "day2_followup", "day": "day2",
             "name": "alpha_%s_%s_followup" % (sector, lang),
             "sector": sector, "language": lang, "body": day2,
             "variables": ["{company_name}"]},
        ]
    return {s: out[s] for s in ("clinics", "real_estate", "restaurants",
                                "salons", "lawyers")}


TEMPLATES = _build()
LATE_TEMPLATES = {
    lang: {"id": "wa_any_%s_day7" % lang, "category": "day7_nudge",
           "day": "day7", "name": "alpha_nudge_%s_v1" % lang,
           "sector": "any", "language": lang, "body": body,
           "variables": ["{company_name}"]}
    for lang, body in _LATE.items()}


# ───────────────────────── public API ─────────────────────────

def get_templates(sector: str, language: str) -> list[dict]:
    """Both steps for one sector and language. KeyError if unknown."""
    return [dict(t) for t in TEMPLATES[sector][language]]


def get_sequence(sector: str, language: str) -> list[dict]:
    """[day0, day2], in order."""
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return sorted(get_templates(sector, language),
                  key=lambda t: order[t["category"]])


def late_template(language: str) -> dict:
    """The day7 nudge for a language. KeyError if unknown."""
    return dict(LATE_TEMPLATES[language])


def get_template_by_id(template_id: str) -> dict | None:
    for langs in TEMPLATES.values():
        for items in langs.values():
            for t in items:
                if t["id"] == template_id:
                    return dict(t)
    for t in LATE_TEMPLATES.values():
        if t["id"] == template_id:
            return dict(t)
    return None


def list_all_ids() -> list[str]:
    """The 20 sector templates (the day7 nudges are separate)."""
    return [t["id"] for langs in TEMPLATES.values()
            for items in langs.values() for t in items]


def all_templates(include_late: bool = True) -> list[dict]:
    out = [get_template_by_id(i) for i in list_all_ids()]
    return out + ([dict(t) for t in LATE_TEMPLATES.values()]
                  if include_late else [])


def company_param(prospect) -> str:
    """The {company_name} value as Meta accepts it: one line, no tabs,
    no runs of spaces, at most 60 characters."""
    p = prospect if isinstance(prospect, dict) else {}
    return " ".join(str(p.get("company_name") or "").split())[:60].rstrip()


def preview_text(template: dict, prospect) -> str:
    return str((template or {}).get("body", "")).replace(
        "{company_name}", company_param(prospect) or "{company_name}")


def render(template: dict, prospect) -> dict:
    """{"template_name", "language", "variables": [{"type": "text",
    "text": value}]} — the parts of a Meta template message. Also
    "template_id" and "preview" (the text the person will read)."""
    t = template or {}
    return {"template_name": t.get("name", ""),
            "language": t.get("language", ""),
            "variables": [{"type": "text", "text": company_param(prospect)}],
            "template_id": t.get("id", ""),
            "preview": preview_text(t, prospect)}


def to_meta_body(body: str) -> str:
    """{company_name} -> {{1}}, the form Meta stores."""
    return str(body or "").replace("{company_name}", "{{1}}")


def export_for_meta_submission(include_late: bool = True) -> list[dict]:
    """Payloads for POST /{WABA_ID}/message_templates — prepared only,
    never submitted from here."""
    return [{"name": t["name"], "language": t["language"],
             "category": META_CATEGORY,
             "components": [{"type": "BODY", "text": to_meta_body(t["body"]),
                             "example": {"body_text": [[EXAMPLE_COMPANY]]}}]}
            for t in all_templates(include_late)]


# ───────────────────────── checks (used by tests and the page) ─────────

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")
_LINK = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|ae|sa|net|org|io)\b",
                   re.I)
_PHONE = re.compile(r"\+?\d[\d\s\-]{6,}\d")
_BANNED = re.compile(r"\b(guarantee[ds]?|free|urgent|click here)\b", re.I)
_CAPS = re.compile(r"\b[A-Z]{3,}\b")
_NAME = re.compile(r"^[a-z0-9_]+$")


def problems(template: dict) -> list[str]:
    """Why Meta (or our rules) would object to a template; [] if none."""
    t = template or {}
    body = str(t.get("body", ""))
    out = []
    if len(body) > MAX_CHARS:
        out.append("over %d characters (%d)" % (MAX_CHARS, len(body)))
    if set(re.findall(r"\{(\w+)\}", body)) != {"company_name"} or \
            body.count("{company_name}") != 1:
        out.append("must use {company_name} exactly once")
    if body.startswith("{") or body.rstrip().endswith("}"):
        out.append("variable at the start or end")
    if _EMOJI.search(body):
        out.append("emoji")
    if _LINK.search(body):
        out.append("link")
    if _PHONE.search(body):
        out.append("phone number")
    if _BANNED.search(body):
        out.append("banned word")
    if _CAPS.search(body):
        out.append("all-caps word")
    if not body.rstrip().endswith(("?", "؟")):
        out.append("does not end with a question")
    if not _NAME.match(str(t.get("name", ""))):
        out.append("template name must be lowercase with underscores")
    return out
