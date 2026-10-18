# -*- coding: utf-8 -*-
"""Indoctrination Campaign — Build trust with a 5-email sequence."""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd

from ui_common import page_config, render_sidebar, page_header
from ui.i18n import t, get_lang
from atlas_services import indoctrination_engine as engine

page_config(st, "Indoctrination Campaign")
render_sidebar(st)
lang = get_lang()
page_header(st, "Indoctrination Campaign", 
            "Build trust and authority with a 5-email sequence before selling.", 
            "mail")

PROSPECTS_DIR = Path(__file__).resolve().parent.parent / "data" / "prospects"

# ══════════════════════════════════════════════════════════
# 1. Stats Dashboard
# ══════════════════════════════════════════════════════════
stats = engine.get_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total in Sequence", stats.get("total", 0))
c2.metric("Active (Warming up)", stats.get("active", 0) + stats.get("dry_run", 0))
c3.metric("Completed (5 emails)", stats.get("completed", 0))
c4.metric("Replied / Stopped", stats.get("replied", 0))

st.divider()

# ══════════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["Start Campaign", "Active Prospects", "Process Due (Manual)"])

# ── TAB 1: Start Campaign ──
with tab1:
    st.subheader("Start Indoctrination for New Prospects")
    st.caption("Select a JSON file from your generated prospects. We recommend using `ready_to_send.json`.")
    
    # Get all json files, sorted by newest
    all_files = sorted(PROSPECTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    # Filter out intermediate files to reduce clutter
    ignore_prefixes = ("finder_", "enriched_", "cleaned_")
    valid_files = [f.name for f in all_files if not f.name.startswith(ignore_prefixes) and f.name != "seen.json"]
    
    if not valid_files:
        st.warning("No suitable files found in data/prospects/. Please run the Finder/Cleaner first.")
    else:
        selected_file = st.selectbox("Select prospects file", valid_files)
        
        col1, col2 = st.columns(2)
        with col1:
            language = st.selectbox("Language", ["en", "ar"])
        with col2:
            dry_run = st.checkbox("Dry run (no real emails sent)", value=True)
            
        if st.button("Start Sequence", type="primary"):
            file_path = PROSPECTS_DIR / selected_file
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                companies = data.get("companies", [])
                
                if not companies:
                    st.warning(f"File `{selected_file}` contains no companies.")
                else:
                    with st.spinner(f"Starting sequence for {len(companies)} prospects..."):
                        success, failed = 0, 0
                        for c in companies:
                            res = engine.start_sequence(c, language=language, dry_run=dry_run, confirmed=not dry_run)
                            if res.get("ok"):
                                success += 1
                            else:
                                failed += 1
                        st.success(f"✅ Started for {success} prospects. Skipped/Failed: {failed}.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

# ── TAB 2: Active Prospects ──
with tab2:
    st.subheader("Prospects Currently in Sequence")
    state = engine._load_state()
    
    if not state:
        st.info("No prospects in the sequence yet. Start a campaign from the first tab.")
    else:
        rows = []
        for email, data in state.items():
            rows.append({
                "Email": email,
                "Company": data.get("company_name", ""),
                "Status": data.get("status", ""),
                "Last Sent": data.get("last_sent_day", ""),
                "Language": data.get("language", ""),
                "Started At": data.get("started_at", "")[:10]
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── TAB 3: Process Due ──
with tab3:
    st.subheader("Process Due Emails")
    st.caption("This is normally handled automatically by the daily automation. You can trigger it manually here for testing.")
    
    dry_run_manual = st.checkbox("Dry run (manual processing)", value=True, key="manual_process_dry")
    
    if st.button("Process Due Emails Now"):
        with st.spinner("Processing..."):
            res = engine.process_due(dry_run=dry_run_manual, confirmed=not dry_run_manual)
            st.success(f"✅ Processed. Sent: {res['sent']}, Blocked: {res['blocked']}, Failed: {res['failed']}.")
            if res['sent'] > 0:
                st.rerun()

st.divider()
st.caption("💡 The engine sends Day 0, Day 1, Day 3, Day 5, and Day 7. If a prospect replies, the sequence stops.")