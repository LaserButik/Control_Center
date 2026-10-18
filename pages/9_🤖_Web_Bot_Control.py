# -*- coding: utf-8 -*-
"""Web Bot Control — Start/Stop the Web_Bot_Project bot."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd

from ui_common import page_config, render_sidebar, page_header, ROOT
from ui import components as C
from ui.i18n import t, get_lang
from connectors import web_bot

page_config(st, "Web Bot Control")
render_sidebar(st)

lang = get_lang()
page_header(st, t("webbot.title", lang), "", "bot")

# ══════════════════════════════════════════════════════
# Status
# ══════════════════════════════════════════════════════
running = web_bot.is_running()
pid = web_bot.read_pid()

status_label = t("webbot.running", lang) if running else t("webbot.stopped", lang)
st.metric(t("webbot.status", lang), status_label)

if running and pid:
    st.caption(f"PID: `{pid}`")

# ══════════════════════════════════════════════════════
# Targets
# ══════════════════════════════════════════════════════
C.render(st, C.section_header(t("webbot.targets", lang)))

url_text = st.text_area(
    t("webbot.url_list", lang),
    height=150,
    key="bot_urls",
    placeholder="https://example.com\nhttps://another.com",
)

visits_per = st.number_input(
    t("webbot.visits_per_url", lang),
    min_value=1, max_value=100, value=5,
    key="bot_visits",
)

randomize = st.checkbox(t("webbot.randomize", lang), key="bot_randomize")

urls = [u.strip() for u in (url_text or "").splitlines() if u.strip()]

if urls:
    preview = [{"URL": u, "Visits": visits_per, "Total": visits_per} for u in urls]
    st.caption(t("webbot.preview", lang))
    st.dataframe(pd.DataFrame(preview), width="stretch", hide_index=True)
    st.caption(f"**Total visits: {visits_per * len(urls)}**")

# ══════════════════════════════════════════════════════
# Start / Stop buttons
# ══════════════════════════════════════════════════════
col = st.columns(2)

with col[0]:
    start_disabled = running or not urls
    if st.button(
        t("webbot.start", lang),
        type="primary",
        icon=":material/play_arrow:",
        disabled=start_disabled,
    ):
        targets = [{"url": u, "visits": visits_per} for u in urls]
        res = web_bot.start_bot(targets=targets, randomize=randomize)
        if res.get("ok"):
            st.success(f"Started, PID {res.get('pid')}")
            st.rerun()
        else:
            st.error(f"Could not start: {res.get('reason')}")

with col[1]:
    if st.button(
        t("webbot.stop", lang),
        icon=":material/stop:",
        disabled=not running,
    ):
        res = web_bot.stop_bot()
        if res.get("ok"):
            st.success("Bot stopped.")
            st.rerun()
        else:
            st.warning(res.get("reason"))

# ══════════════════════════════════════════════════════
# Statistics
# ══════════════════════════════════════════════════════
st.divider()
C.render(st, C.section_header("Statistics"))

try:
    stats = web_bot.get_stats()
    c = st.columns(4)
    c[0].metric("Total", stats.get("total", 0))
    c[1].metric("Success", stats.get("success", 0))
    c[2].metric("Failed", stats.get("failed", 0))
    c[3].metric("Success rate", "%.1f%%" % stats.get("success_rate", 0))
except Exception as e:
    st.warning(f"Stats unavailable: {e}")

# ══════════════════════════════════════════════════════
# Recent sessions
# ══════════════════════════════════════════════════════
C.render(st, C.section_header("Recent sessions"))

try:
    df = web_bot.read_sessions(limit=50)
    if not df.empty:
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No sessions recorded yet.")
except Exception as e:
    st.warning(f"Sessions unavailable: {e}")

st.caption("↻ Click F5 to refresh status.")