# -*- coding: utf-8 -*-
"""ATLAS — Prospect Enrichment: emails, phones, decision-makers and social
links from each company's OWN public website. robots.txt honoured, max 3
pages per company, delays between requests. Output goes to
Control_Center/data/enrichment/. Reads the outreach run read-only."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402  (loads .env first)

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar, page_header
from ui import components as C
from ui.icons import ICONS
from connectors import paths
from atlas_services import prospect_enricher as PE

page_config(st, "ATLAS Enrichment")
render_sidebar(st)

page_header(st, "ATLAS — Prospect Enrichment",
            "Extract emails, phones, decision-makers from company websites.",
            "search")

DEFAULT_INPUT = paths.OUTREACH_RUNS / "20261007T053653Z" / "prospects.json"
OUT_DIR = paths.CC_DATA / "enrichment"

# ── input ──
C.render(st, C.section_header("Prospects", "A prospects JSON from an "
                              "outreach run, or any list of companies with "
                              "a website field."))
src = st.radio("Source", ["Path", "Upload JSON"], horizontal=True)
companies, err = [], None
if src == "Path":
    path = st.text_input("Prospects file", value=str(DEFAULT_INPUT))
    if path:
        try:
            companies = PE.load_companies(path)
        except (OSError, ValueError) as e:
            err = "Cannot read %s (%s)" % (path, type(e).__name__)
else:
    up = st.file_uploader("Prospects JSON", type=["json"])
    if up:
        try:
            data = json.loads(up.getvalue().decode("utf-8"))
            rows = data.get("prospects", data.get("results", data)) \
                if isinstance(data, dict) else data
            companies = [r for r in rows if isinstance(r, dict)
                         and not r.get("skipped")]
        except (ValueError, UnicodeDecodeError) as e:
            err = "Cannot read the upload (%s)" % type(e).__name__
if err:
    C.render(st, C.status_pill(err, "danger"))

with_site = sum(1 for c in companies if PE._base(c.get("website") or ""))
C.render(st, C.kpi_grid([
    {"label": "Companies loaded", "value": len(companies),
     "icon_svg": ICONS["users"]},
    {"label": "With a website", "value": with_site,
     "icon_svg": ICONS["globe"],
     "trend": "up" if with_site else "down",
     "delta": "%d without" % (len(companies) - with_site)
     if companies else ""},
], columns=2))

if companies and not with_site:
    C.render(st, C.glass_card(
        "No websites in this file",
        "None of these companies has a <b>website</b> field, so enrichment "
        "would skip every one of them (<i>no_website</i>). The DHCC export "
        "carries names, phones and activities but no websites. Add a "
        "<code>website</code> to each company first (by hand, or from a "
        "source that lists them), then enrich.", accent="warning"))

# ── settings ──
C.render(st, C.section_header("Settings"))
s1, s2, s3 = st.columns(3)
max_n = s1.number_input("Max companies", 1, 100, 30)
delay = s2.number_input("Delay between companies (s)", 2.0, 60.0, 3.0,
                        step=0.5)
dry = s3.checkbox("Dry run (no network)", value=False,
                  help="Lists what would be visited; fetches nothing.")
C.render(st, "<div style='color:#6B7689;font-size:12.5px;'>Per company: "
         "robots.txt first, at most 3 pages of its own site, 2 s between "
         "pages, 10 s timeout. No external links are followed.</div>")

run = st.button("Enrich", type="primary", icon=":material/search:",
                disabled=not companies)

if run:
    total = min(len(companies), int(max_n))
    bar = st.progress(0.0, text="0/%d" % total)
    log_box = st.empty()
    log = []

    def on_progress(done, n, r):
        status = r.get("enrichment_status")
        log.append("%2d/%d  %-8s %s%s" % (
            done, n, status, (r.get("company_name") or "-")[:40],
            ("  <%s>" % r["email"]) if r.get("email") else ""))
        bar.progress(done / max(1, n), text="%d/%d" % (done, n))
        log_box.markdown(C.code_block("\n".join(log[-10:]), "live log"),
                         unsafe_allow_html=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / ("enriched_%s.json" % stamp)
    with st.spinner("Enriching %d compan%s…" % (total,
                                                 "y" if total == 1 else "ies")):
        res = PE.enrich_many(companies, max_companies=int(max_n),
                             out_path=str(out_path),
                             sleep_between_companies_s=float(delay),
                             dry_run=bool(dry), on_progress=on_progress)
    st.session_state["enrich_result"] = res

res = st.session_state.get("enrich_result")
if res:
    C.render(st, C.section_header("Result", "Saved to %s" % res["out_path"]))
    C.render(st, C.kpi_grid([
        {"label": "Enriched (email)", "value": res["enriched"],
         "icon_svg": ICONS["check"], "trend": "up" if res["enriched"]
         else "flat"},
        {"label": "Partial", "value": res["partial"],
         "icon_svg": ICONS["activity"]},
        {"label": "Skipped", "value": res["skipped"],
         "icon_svg": ICONS["alert"],
         "delta": ", ".join("%s %d" % kv for kv in
                            res["skipped_reasons"].items()),
         "trend": "down" if res["skipped"] else "flat"},
        {"label": "Network calls", "value": res["network_calls"],
         "icon_svg": ICONS["globe"],
         "delta": "%.1f s" % (res["duration_ms"] / 1000)},
    ], columns=4))
    table = pd.DataFrame([{
        "company": r.get("company_name"),
        "email": r.get("email") or "",
        "phone": (r.get("phones_all") or [r.get("phone_e164") or ""])[0],
        "linkedin": (r.get("social_links") or {}).get("linkedin") or "",
        "decision makers": "; ".join("%s (%s)" % (d["name"], d["role"])
                                     for d in r.get("decision_makers", [])),
        "status": r.get("enrichment_status")} for r in res["results"]])
    st.dataframe(table, width="stretch", hide_index=True)
    st.download_button("Download enriched JSON",
                       json.dumps(res["results"], ensure_ascii=False,
                                  indent=1).encode("utf-8"),
                       file_name=Path(res["out_path"]).name,
                       mime="application/json",
                       icon=":material/download:")
    C.render(st, C.glass_card(
        "Before you use these",
        "Always review emails before sending. Names of founders and "
        "managers are personal data under the UAE and Saudi PDPL, even on a "
        "public page — keep them only for this outreach and honour any "
        "opt-out.", accent="warning"))
