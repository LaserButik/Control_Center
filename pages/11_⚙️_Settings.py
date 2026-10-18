# -*- coding: utf-8 -*-
"""Settings: language, sending limits, sender identity, environment,
and system tools. Reads and writes data/settings.json (non-secret)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402

import streamlit as st

from ui_common import page_config, render_sidebar, page_header, ROOT
from ui import components as C
from ui.i18n import t, get_lang, set_lang
from ui.settings_store import load_settings, save_settings, reset_settings, DEFAULTS

page_config(st, "Settings")
render_sidebar(st)

lang = get_lang()
page_header(st, t("settings.title", lang), t("settings.subtitle", lang),
            "settings")

settings = load_settings()

# ---- Section 1: Language ----
C.render(st, C.section_header(t("settings.language", lang)))
lang_choice = st.radio(
    t("settings.language", lang),
    ["en", "ar"],
    index=0 if settings.get("language", "en") == "en" else 1,
    format_func=lambda x: "English" if x == "en" else "العربية",
    horizontal=True,
    key="settings_lang",
    label_visibility="collapsed",
)
if lang_choice != settings.get("language", "en"):
    settings["language"] = lang_choice
    save_settings(settings)
    set_lang(lang_choice)
    st.rerun()

# ---- Section 2: Sending ----
C.render(st, C.section_header(t("settings.sending", lang)))
from atlas_services.email_sender import MAX_DAILY_LIMIT as EMAIL_CAP  # noqa: E402
from atlas_services.whatsapp_sender import MAX_DAILY_LIMIT as WA_CAP  # noqa: E402

c1, c2 = st.columns(2)
email_limit = c1.number_input(
    t("settings.daily_email_limit", lang),
    min_value=1, max_value=EMAIL_CAP,
    value=min(int(settings.get("daily_email_limit", EMAIL_CAP)), EMAIL_CAP),
    key="settings_email_limit",
)
wa_limit = c2.number_input(
    t("settings.daily_whatsapp_limit", lang),
    min_value=1, max_value=WA_CAP,
    value=min(int(settings.get("daily_whatsapp_limit", WA_CAP)), WA_CAP),
    key="settings_wa_limit",
)
st.caption(t("settings.limits_caption", lang)
           .replace("{email}", str(EMAIL_CAP)).replace("{wa}", str(WA_CAP)))

# ---- Section 3: Sender Identity ----
C.render(st, C.section_header(t("settings.sender_identity", lang)))
sender_name = st.text_input(
    t("settings.sender_name", lang),
    value=settings.get("sender_name", DEFAULTS["sender_name"]),
    key="settings_sender_name",
)
sender_title = st.text_input(
    t("settings.sender_title", lang),
    value=settings.get("sender_title", DEFAULTS["sender_title"]),
    key="settings_sender_title",
)
physical_address = st.text_input(
    t("settings.physical_address", lang),
    value=settings.get("physical_address", DEFAULTS["physical_address"]),
    key="settings_address",
)

# save sending + identity
if st.button(t("common.save", lang), type="primary", key="save_settings"):
    settings["daily_email_limit"] = email_limit
    settings["daily_whatsapp_limit"] = wa_limit
    settings["sender_name"] = sender_name
    settings["sender_title"] = sender_title
    settings["physical_address"] = physical_address
    save_settings(settings)
    st.success(t("settings.saved", lang))

# ---- Section 4: Environment (read-only) ----
C.render(st, C.section_header(t("settings.environment", lang)))
status = config.env_status()
for name, ok in status.items():
    if ok:
        C.render(st, C.status_pill(
            t("settings.env_configured", lang).replace("{name}", name),
            "success"))
    else:
        C.render(st, C.status_pill(
            t("settings.env_missing", lang).replace("{name}", name),
            "warning"))
with st.expander(t("settings.show_template", lang)):
    st.code("""SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=<your Brevo SMTP login>
SMTP_PASSWORD=<your Brevo SMTP key>
SMTP_FROM=info@salehhaidar.com
WHATSAPP_PHONE_ID=<from Meta>
WHATSAPP_TOKEN=<from Meta>
SERPER_API_KEY=<your key>
TELEGRAM_BOT_TOKEN=<from BotFather>
TELEGRAM_CHAT_ID=<your chat id>""", language="dotenv")

# ---- Section 5: System ----
C.render(st, C.section_header(t("settings.system", lang)))
st.code(str(ROOT), language="text")
settings_path = ROOT / "data" / "settings.json"
if settings_path.is_file():
    st.download_button(
        t("settings.backup", lang),
        settings_path.read_bytes(),
        file_name="settings.json",
        mime="application/json",
        icon=":material/download:",
        key="backup_settings",
    )
if st.button(t("settings.reset", lang), key="reset_settings"):
    st.session_state["confirm_reset"] = True
if st.session_state.get("confirm_reset"):
    st.warning(t("settings.reset_confirm", lang))
    r1, r2 = st.columns(2)
    if r1.button(t("common.confirm", lang), key="confirm_reset_yes"):
        reset_settings()
        st.session_state.pop("confirm_reset", None)
        st.rerun()
    if r2.button(t("common.cancel", lang), key="confirm_reset_no"):
        st.session_state.pop("confirm_reset", None)
        st.rerun()
