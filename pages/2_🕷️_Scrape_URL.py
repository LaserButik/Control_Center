# -*- coding: utf-8 -*-
"""Run the outreach one-page scraper on a single URL.

Dry Run previews the exact command and fetches nothing. Real Scrape runs
outreach.real_scrape in the outreach venv: robots.txt fetched and enforced,
exactly one page read, rows written with is_test=true. Nothing is sent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import (page_config, render_sidebar, page_header,
                       show_result, show_command)
from ui import components as C
from ui.i18n import t, get_lang
from connectors import outreach, paths

lang = get_lang()
page_config(st, t("scrape.page_title", lang))
render_sidebar(st)

page_header(st, t("scrape.title", lang), t("scrape.subtitle", lang),
            "spider")

C.render(st, C.glass_card(t("scrape.before_title", lang),
                          t("scrape.before_body", lang), accent="warning"))

C.render(st, C.section_header(t("scrape.target", lang),
                              t("scrape.target_sub", lang)))
with st.container(border=True):
    url = st.text_input(t("scrape.url_label", lang),
                        placeholder="https://directory.example/companies")
    s1, s2 = st.columns(2)
    max_prospects = s1.slider(t("scrape.max_prospects", lang), 1, 10, 5,
                              help=t("scrape.max_help", lang))
    delay = s2.slider(t("scrape.delay", lang), 5, 120, 5,
                      help=t("scrape.delay_help", lang))
    ack = st.checkbox(t("scrape.ack", lang))

b1, b2, _ = st.columns([1, 1, 3])
dry = b1.button(t("scrape.dry", lang), icon=":material/visibility:",
                width="stretch", disabled=not url)
real = b2.button(t("scrape.real", lang), type="primary",
                 icon=":material/travel_explore:", width="stretch",
                 disabled=not (url and ack))
if url and not ack:
    C.render(st, C.status_pill(t("scrape.tick_terms", lang), "warning"))

if dry:
    C.render(st, C.section_header(t("scrape.dry_header", lang),
                                  t("scrape.dry_sub", lang)))
    show_command(st, [paths.outreach_python(), "-m",
                      *outreach.scrape_argv(url, max_prospects, delay)])

if real:
    C.render(st, C.section_header(t("scrape.result", lang)))
    with st.spinner(t("scrape.scraping", lang).replace("{n}", str(delay))):
        result = outreach.scrape_url(url, int(max_prospects), float(delay))
    show_result(st, result)
