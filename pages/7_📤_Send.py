# -*- coding: utf-8 -*-
"""Pick a run, dry-run the WhatsApp send, then (with a confirm checkbox)
run the real send through the outreach pipeline's own gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar, show_result
from ui_common import page_header
from ui import components as C
from ui.icons import ICONS
from ui.i18n import t, get_lang
from connectors import outreach

lang = get_lang()
page_config(st, t("send.page_title", lang))
render_sidebar(st)

page_header(st, t("send.title", lang), "", "send")
st.caption(t("send.caption", lang))

runs = [r for r in outreach.list_runs() if r["has_queue"]]
if not runs:
    C.render(st, C.empty_state(t("common.nothing_yet", lang),
                               t("common.no_queue_runs", lang),
                               ICONS["inbox"]))
    st.stop()

run_id = st.selectbox(t("common.run", lang), [r["run_id"] for r in runs])
data = outreach.load_run(run_id)
approved = sum(1 for e in data.get("entries", [])
               if e.get("status") == "approved")
st.metric(t("send.approved", lang), approved)

col = st.columns(2)
tname = col[0].text_input(t("send.template_name", lang),
                          value=outreach.DEFAULT_TEMPLATE_NAME)
tlang = col[1].text_input(t("send.template_lang", lang),
                          value=outreach.DEFAULT_TEMPLATE_LANGUAGE)
st.caption(t("send.verified", lang)
           .replace("{name}", outreach.DEFAULT_TEMPLATE_NAME)
           .replace("{lang}", outreach.DEFAULT_TEMPLATE_LANGUAGE))
tname, tlang = outreach.resolve_template(tname, tlang)

C.render(st, C.section_header(t("send.step_dry", lang)))
if st.button(t("send.run_dry", lang), type="primary"):
    with st.spinner(t("send.dry_running", lang)):
        show_result(st, outreach.send_whatsapp(
            run_id, confirmed=False, template_name=tname,
            template_language=tlang))

st.divider()
C.render(st, C.section_header(t("send.step_real", lang)))
st.warning(t("send.warning", lang))
confirm = st.checkbox(t("send.confirm", lang))
if st.button(t("send.real", lang), disabled=not confirm):
    with st.spinner(t("send.sending", lang)):
        show_result(st, outreach.send_whatsapp(
            run_id, confirmed=True, template_name=tname,
            template_language=tlang))
