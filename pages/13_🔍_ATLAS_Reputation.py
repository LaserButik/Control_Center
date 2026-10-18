# -*- coding: utf-8 -*-
"""ATLAS reputation monitor: brand mentions and sentiment via Serper."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402  (loads .env first)

import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import charts, components as C
from atlas_services import reputation_monitor as REP

page_config(st, "ATLAS Reputation")
render_sidebar(st)

page_header(st, "Reputation monitor", "", "shield")
st.caption("Searches a brand across public results and classifies mentions "
           "as positive / negative / neutral. Needs SERPER_API_KEY in this "
           "environment; without it, no network call is made.")

brand = st.text_input("Brand", placeholder="ACME Dubai")
col = st.columns(2)
country = col[0].text_input("Country code", value="ae")
num = col[1].number_input("Results per query", 1, 20, 20)

if st.button("Check reputation", type="primary", disabled=not brand):
    with st.spinner("Searching…"):
        r = REP.check_brand(brand, country, int(num))
    if not r.get("ok"):
        st.warning("Stopped: %s" % r.get("reason"))
    else:
        m = st.columns(4)
        m[0].metric("Mentions", r["total_mentions"])
        m[1].metric("Positive", r["positive_hits"])
        m[2].metric("Negative", r["negative_hits"])
        m[3].metric("Neutral", r["neutral_hits"])
        g1, g2 = st.columns(2)
        with g1:
            charts.show(st, charts.bars(
                ["Positive", "Negative", "Neutral"],
                [r["positive_hits"], r["negative_hits"],
                 r["neutral_hits"]], title="Sentiment"))
        with g2:
            from collections import Counter
            from urllib.parse import urlsplit
            hosts = Counter((urlsplit(s["url"]).hostname or "?")
                            .removeprefix("www.")
                            for s in r["top_sources"]).most_common(8)
            charts.show(st, charts.bars([h for h, _ in hosts][::-1],
                                        [n for _, n in hosts][::-1],
                                        title="Top sources",
                                        horizontal=True))
        C.render(st, C.section_header("Top sources"))
        st.dataframe(r["top_sources"], width="stretch", hide_index=True)
        with st.expander("Raw result"):
            st.json(r)
        st.session_state["atlas_reputation"] = r
