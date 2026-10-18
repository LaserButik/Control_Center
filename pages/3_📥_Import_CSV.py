# -*- coding: utf-8 -*-
"""Upload an Instant Data Scraper CSV and run the outreach importer."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar, show_result
from ui_common import page_header
from ui.i18n import t, get_lang
from connectors import outreach, paths

lang = get_lang()
page_config(st, t("csv.page_title", lang))
render_sidebar(st)

page_header(st, t("csv.title", lang), "", "upload")
st.caption(t("csv.caption", lang))

uploaded = st.file_uploader(t("csv.uploader", lang), type=["csv"])
source_url = st.text_input(t("csv.source_url", lang),
                           value="https://dhcc.ae/Facilities")

if uploaded and st.button(t("csv.import", lang), type="primary"):
    # The upload is written to the Control Center temp area, never into the
    # other projects.
    tmp_dir = paths.ensure_cc_data() / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(tmp_dir), suffix=".csv")
    import os
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getvalue())
    with st.spinner(t("csv.importing", lang)):
        result = outreach.import_csv(tmp_path, source_url)
    show_result(st, result)
    if result.get("ok"):
        st.success(t("csv.done", lang))
