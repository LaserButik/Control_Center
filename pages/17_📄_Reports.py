# -*- coding: utf-8 -*-
"""Generate PDF reports: one per outreach run, or from an ATLAS result held
in this session. PDFs are written under Control_Center/reports/out/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import components as C
from connectors import outreach, paths
from reports import pdf_generator as PG

page_config(st, "Reports")
render_sidebar(st)

page_header(st, "PDF reports", "", "file")
st.caption("English PDFs via reportlab, written to "
           "Control_Center/reports/out/. Reads outreach data; changes "
           "nothing in it.")

out_dir = paths.CC_ROOT / "reports" / "out"

C.render(st, C.section_header("Outreach run report"))
runs = outreach.list_runs()
if runs:
    run_id = st.selectbox("Run", [r["run_id"] for r in runs])
    if st.button("Generate run report", type="primary"):
        out_path = out_dir / ("run_%s.pdf" % run_id)
        with st.spinner("Building PDF…"):
            r = PG.report_for_run(run_id, str(paths.OUTREACH_DATA),
                                  str(out_path))
        if r.get("ok"):
            st.success("Wrote %s (%d bytes)" % (r["out_path"],
                                               r["size_bytes"]))
            st.download_button("Download PDF",
                               Path(r["out_path"]).read_bytes(),
                               icon=":material/download:", file_name=Path(r["out_path"]).name,
                               mime="application/pdf")
        else:
            st.error("Failed: %s" % r.get("reason"))
else:
    st.info("No outreach runs yet.")

st.divider()
C.render(st, C.section_header("ATLAS result report"))
st.caption("Run a reputation / backlinks / competitive check on its page "
           "first; the latest result is held in this session.")
kinds = {"reputation": "atlas_reputation", "backlinks": "atlas_backlinks",
         "competitive": "atlas_competitive"}
kind = st.selectbox("Report type", list(kinds))
payload = st.session_state.get(kinds[kind])
if payload is None:
    st.info("No %s result in this session yet." % kind)
else:
    if st.button("Generate ATLAS report"):
        out_path = out_dir / ("atlas_%s.pdf" % kind)
        with st.spinner("Building PDF…"):
            r = PG.report_for_atlas(kind, payload, str(out_path))
        if r.get("ok"):
            st.success("Wrote %s" % r["out_path"])
            st.download_button("Download PDF",
                               Path(r["out_path"]).read_bytes(),
                               icon=":material/download:", file_name=Path(r["out_path"]).name,
                               mime="application/pdf")
        else:
            st.error("Failed: %s" % r.get("reason"))
