# -*- coding: utf-8 -*-
"""ATLAS competitive analysis: compare two websites on on-page signals."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402  (loads .env first)

import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import charts
from atlas_services import competitive_analysis as COMP

page_config(st, "ATLAS Competitive")
render_sidebar(st)

page_header(st, "Competitive analysis", "", "sword")
st.caption("Fetches each homepage once and scores on-page signals (title, "
           "meta, viewport, analytics, schema.org, lang, content). No API "
           "key needed. Runs only when you click.")

col = st.columns(2)
a = col[0].text_input("Domain A", placeholder="you.ae")
b = col[1].text_input("Domain B", placeholder="competitor.ae")

if st.button("Compare", type="primary", disabled=not (a and b)):
    with st.spinner("Fetching both homepages…"):
        r = COMP.compare(a, b)
    if not r.get("ok"):
        st.warning("Stopped: %s" % r.get("reason"))
    else:
        m = st.columns(3)
        m[0].metric("Score A", r["score_a"])
        m[1].metric("Score B", r["score_b"])
        m[2].metric("Winner", {"a": a, "b": b, "tie": "tie"}[r["winner"]])
        sig = list(r["probe_a"]["signals"])
        g1, g2 = st.columns([1, 2])
        with g1:
            charts.show(st, charts.bars([a, b], [r["score_a"],
                                                 r["score_b"]],
                                        title="Score (0-100)"))
        with g2:
            charts.show(st, charts.bars(
                [s.replace("_", " ") for s in sig],
                [int(r["probe_a"]["signals"][s]) +
                 int(r["probe_b"]["signals"][s]) for s in sig],
                title="Signals present (0-2 sites)", horizontal=True))
        cols = st.columns(2)
        for col_el, label, probe in ((cols[0], a, r["probe_a"]),
                                     (cols[1], b, r["probe_b"])):
            with col_el:
                st.subheader(label)
                st.json({k: probe[k] for k in
                         ("reachable", "status_code", "title",
                          "meta_description", "html_lang", "content_length",
                          "signals")})
        st.session_state["atlas_competitive"] = r
