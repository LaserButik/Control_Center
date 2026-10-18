# -*- coding: utf-8 -*-
"""Run outreach directory verification (robots / login / ToS). Online only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar, show_result
from ui_common import page_header
from ui.i18n import t, get_lang
from connectors import outreach

lang = get_lang()
page_config(st, t("verify.page_title", lang))
render_sidebar(st)

page_header(st, t("verify.title", lang), "", "check")
st.caption(t("verify.caption", lang))

VERDICTS = {"READY": t("verify.ready", lang),
            "REVIEW": t("verify.review", lang),
            "NO-GO": t("verify.nogo", lang)}

ver = outreach.load_verifications()
results = ver.get("results", [])
if results:
    counts = {v: sum(1 for r in results if r.get("verdict") == v)
              for v in VERDICTS}
    c = st.columns(3)
    for col, (code, label) in zip(c, VERDICTS.items()):
        col.metric(label, counts[code])
    st.dataframe([{t("verify.col_url", lang): r.get("url"),
                   t("verify.col_verdict", lang): VERDICTS.get(
                       r.get("verdict"), r.get("verdict")),
                   t("verify.col_reason", lang): r.get("reason")}
                  for r in results], width="stretch", hide_index=True)
    st.info(t("verify.not_permission", lang))
else:
    st.info(t("verify.none", lang))

st.warning(t("verify.warning", lang))
if st.button(t("verify.run", lang), type="primary"):
    with st.spinner(t("verify.running", lang)):
        result = outreach.verify_run()
    show_result(st, result)
