# -*- coding: utf-8 -*-
"""Run outreach discovery (seeds offline; search + cross-refs when online)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar, show_result
from ui_common import page_header
from ui import components as C
from ui.i18n import t, get_lang
from connectors import outreach

lang = get_lang()
page_config(st, t("disc.page_title", lang))
render_sidebar(st)

page_header(st, t("disc.title", lang), "", "search")
st.caption(t("disc.caption", lang))

online = st.checkbox(t("disc.online", lang), value=False)
if online:
    st.warning(t("disc.online_warning", lang))

C.render(st, C.section_header(t("disc.current", lang)))
disc = outreach.load_discovery()
cands = disc.get("candidates", [])
st.write(t("disc.count", lang).replace("{n}", str(len(cands))))
if cands:
    st.dataframe([{t("disc.col_host", lang): c.get("host"),
                   t("disc.col_country", lang): c.get("country"),
                   t("disc.col_type", lang): c.get("type"),
                   t("disc.col_source", lang): c.get("source")}
                  for c in cands[:50]], width="stretch", hide_index=True)

if st.button(t("disc.run", lang), type="primary"):
    with st.spinner(t("disc.running", lang)):
        result = outreach.discover_run(online=online)
    show_result(st, result)
