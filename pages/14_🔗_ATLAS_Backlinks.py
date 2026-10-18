# -*- coding: utf-8 -*-
"""ATLAS backlink intelligence: referring domains via Serper (estimate)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402  (loads .env first)

import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import charts, components as C
from atlas_services import backlink_intelligence as BL

page_config(st, "ATLAS Backlinks")
render_sidebar(st)

page_header(st, "Backlink intelligence", "", "link")
st.caption("An estimate of referring domains from public search results, "
           "not a crawl of a link index. Needs SERPER_API_KEY; without it, "
           "no network call is made.")

domain = st.text_input("Domain", placeholder="example.ae")
country = st.text_input("Country code", value="us")

if st.button("Check backlinks", type="primary", disabled=not domain):
    with st.spinner("Searching…"):
        r = BL.check_backlinks(domain, country)
    if not r.get("ok"):
        st.warning("Stopped: %s" % r.get("reason"))
    else:
        m = st.columns(2)
        m[0].metric("Estimated backlinks", r["estimated_backlinks"])
        m[1].metric("Referring domains", r["referring_domains_count"])
        from collections import Counter
        tlds = Counter(d.rsplit(".", 1)[-1] for d in
                       r["referring_domains_sample"]).most_common(10)
        if tlds:
            charts.show(st, charts.bars(
                [t for t, _ in tlds], [n for _, n in tlds],
                title="Referring domains by TLD (sample)"))
        C.render(st, C.section_header("Top referrers"))
        st.dataframe(r["top_referrers"], width="stretch", hide_index=True)
        with st.expander("Referring domains (sample)"):
            st.write(r["referring_domains_sample"])
        st.session_state["atlas_backlinks"] = r
