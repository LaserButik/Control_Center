# -*- coding: utf-8 -*-
"""Shared page plumbing: path bootstrap, theme injection, the custom sidebar."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from connectors import alpha, outreach, paths, web_bot
from ui import components as C
from ui.icons import ICONS, icon
from ui.theme import inject_global_css
from ui.i18n import t, get_lang, set_lang, is_rtl

PAGES_DIR = ROOT / "pages"

# تحديث اسم الصفحة إلى Sales & Replies
SIDEBAR_GROUPS = {
    "overview": {
        "label": "nav.section.overview",
        "pages": [
            ("app", "nav.home", ":material/home:"),
        ],
    },
    "pipeline": {
        "label": "nav.section.pipeline",
        "pages": [
            (20, "nav.find_prospects", ":material/person_search:"),
            (2, "nav.scrape_url", ":material/language:"),
            (3, "nav.import_csv", ":material/upload_file:"),
            (4, "nav.discovery", ":material/explore:"),
            (5, "nav.verify", ":material/verified:"),
            (12, "nav.prospects", ":material/people:"),
            (6, "nav.review_queue", ":material/checklist:"),
            (19, "nav.enrichment", ":material/auto_fix_high:"),
            (7, "nav.send", ":material/send:"),
            (8, "nav.sales_replies", ":material/inbox:"), # تم تغيير الاسم هنا
        ],
    },
    "atlas": {
        "label": "nav.section.atlas",
        "pages": [
            (21, "nav.email", ":material/mail:"),
            (22, "nav.whatsapp", ":material/chat:"),
            (24, "nav.outreach_reports", ":material/bar_chart:"),
            (17, "nav.reports", ":material/description:"),
            (10, "nav.atlas_services", ":material/hub:"),
            (13, "nav.reputation", ":material/star:"),
            (14, "nav.backlinks", ":material/link:"),
            (15, "nav.competitive", ":material/compare_arrows:"),
            (16, "nav.ab_testing", ":material/science:"),
            (18, "nav.distribution", ":material/share:"),
        ],
    },
    "system": {
        "label": "nav.section.system",
        "pages": [
            (25, "nav.daily_automation", ":material/schedule:"),
            (9, "nav.web_bot", ":material/smart_toy:"),
            (27, "nav.indoctrination", ":material/security:"),
            (29, "nav.social_media", ":material/share:"),
                        (30, "nav.funnel_analytics", ":material/analytics:"),
        ],
    },
}


def _page_path(num) -> str | None:
    if num == "app":
        return "app.py"
    for p in PAGES_DIR.glob("%d_*.py" % num):
        return "pages/" + p.name
    return None


def page_config(st, title: str, icon_name: str = "") -> None:
    st.set_page_config(page_title="%s · %s" % (title, t("common.app_name")),
                       page_icon=":material/hub:", layout="wide",
                       initial_sidebar_state="expanded")
    inject_global_css()


def page_header(st, title: str, subtitle: str = "", icon_key: str = "sparkle") -> None:
    C.render(st, C.hero(title, subtitle, ICONS.get(icon_key, ICONS["sparkle"])))


def render_sidebar(st) -> None:
    lang = get_lang()
    with st.sidebar:
        C.render(st, C.wordmark("AI Mentors", t("common.app_name", lang)))
        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("EN", type="primary" if lang == "en" else "secondary",
                         key="sb_en", use_container_width=True):
                set_lang("en")
                st.rerun()
        with _c2:
            if st.button("AR", type="primary" if lang == "ar" else "secondary",
                         key="sb_ar", use_container_width=True):
                set_lang("ar")
                st.rerun()
        from ui.settings_store import load_settings
        group_state = load_settings().get(
            "sidebar_groups",
            {"overview": True, "pipeline": True, "atlas": True, "system": True})
        for group_key, group in SIDEBAR_GROUPS.items():
            expanded = group_state.get(group_key, True)
            with st.expander(t(group["label"], lang), expanded=expanded):
                for num, label_key, mat in group["pages"]:
                    path = _page_path(num)
                    if not path:
                        continue
                    try:
                        st.page_link(path, label=t(label_key, lang), icon=mat)
                    except Exception:
                        st.markdown("<span style='color:#718096;font-size:13px;"
                                    "padding-left:12px;'>%s</span>"
                                    % t(label_key, lang),
                                    unsafe_allow_html=True)
        C.render(st, C.divider())
        settings_path = _page_path(11)
        if settings_path:
            try:
                st.page_link(settings_path, label=t("nav.settings", lang),
                             icon=":material/tune:")
            except Exception:
                pass
        st.write("")
        if st.button(t("common.refresh", lang), icon=":material/refresh:",
                     width="stretch"):
            st.rerun()