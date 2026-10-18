# -*- coding: utf-8 -*-
"""ATLAS — Prospect Finder: new prospects with emails from public search
(Serper) or public directory listings (Playwright). Dry run is the
default and makes no request. Results go to Control_Center/data/prospects/.
"""

import json
import os
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
from atlas_services import prospect_finder as PF

page_config(st, "ATLAS Finder")
render_sidebar(st)

page_header(st, "ATLAS — Prospect Finder",
            "Find new prospects with emails from public directories and "
            "search.", "users")

# ── mode ──
C.render(st, C.section_header("Mode"))
mode_label = st.radio("Mode", ["Serper (fast, uses SERPER_API_KEY)",
                               "Playwright (deep, crawls directories)"],
                      label_visibility="collapsed")
mode = "serper" if mode_label.startswith("Serper") else "playwright"
if mode == "serper":
    has_key = bool(os.getenv("SERPER_API_KEY"))
    C.render(st, C.status_pill("SERPER_API_KEY %s in this environment"
                               % ("found" if has_key else "NOT set"),
                               "success" if has_key else "danger"))
else:
    C.render(st, C.glass_card(
        "Directory sources (inspected 2026-10-07)",
        "<b>Yello UAE</b> is the only working source: category listings "
        "with company names, cities and phones, but <b>no emails</b> on the "
        "listing pages (company pages are not opened in this mode). "
        "Connect AE no longer resolves; Maroof SA answered robots.txt with "
        "HTTP 503 and is a government platform, so both are disabled. "
        "Saudi Arabia has no enabled source.<br>Needs the browser once: "
        "<code>.\\venv\\Scripts\\python.exe -m playwright install "
        "chromium</code>", accent="warning"))

# ── filters ──
C.render(st, C.section_header("Filters"))
f1, f2, f3 = st.columns([3, 1, 1])
sectors = f1.multiselect("Sectors", list(PF.SECTORS),
                         default=list(PF.SECTORS))
country = f2.selectbox("Country", ["AE", "SA"])
max_n = f3.number_input("Max results per sector", 4, 100, 20)

# ── options ──
C.render(st, C.section_header("Options"))
o1, o2, o3 = st.columns(3)
dry = o1.checkbox("Dry run (no network, just plan)", value=True)
save = o2.checkbox("Save to file (data/prospects/)", value=True)
strict = o3.checkbox("Apply strict filters", value=True,
                     help="Drops page titles, documents, news pages and "
                          "directory/social sites; clears foreign phones; "
                          "marks off-domain emails as low confidence. "
                          "Serper mode only.")

REASON_LABELS = {"title_like_name": "Page title, not a name",
                 "blocked_domain": "Blocked domain",
                 "document_source": "Document or news page"}
CLEAN_LABELS = {"phone_wrong_country": "Foreign phone cleared",
                "email_domain_mismatch": "Email off-domain (low)",
                "sector_mismatch": "Sector set to unknown"}


def filtering_report(stats: dict, strict_on: bool, note: str = "") -> None:
    """The "Filtering report" expander: counts by reason, then the
    rejected companies with a JSON download."""
    rej, cleaned = stats["companies_rejected"], stats["companies_cleaned"]
    rows = stats["rejected_companies"]
    with st.expander("Filtering report (%d rejected)" % rej["total"]):
        if not strict_on:
            C.render(st, C.status_pill("Strict filters were off for this "
                                       "run: nothing was filtered.",
                                       "warning"))
        elif note:
            C.render(st, C.status_pill(note, "info"))
        C.render(st, C.kpi_grid(
            [{"label": REASON_LABELS[k], "value": rej[k],
              "icon_svg": ICONS["x"]} for k in PF.REJECT_REASONS] +
            [{"label": CLEAN_LABELS[k], "value": cleaned[k],
              "icon_svg": ICONS["filter"]} for k in PF.CLEAN_KINDS],
            columns=3))
        if rows:
            st.dataframe(pd.DataFrame([{
                "company_name": x.get("company_name") or "",
                "source_url": x.get("source_url") or "",
                "reason": x.get("reason")} for x in rows]),
                width="stretch", hide_index=True)
            st.download_button("Download rejected (JSON)",
                               json.dumps(rows, ensure_ascii=False,
                                          indent=1).encode("utf-8"),
                               file_name="finder_rejected.json",
                               mime="application/json",
                               icon=":material/download:",
                               key="dl_rejected")

run = st.button("Find Prospects", type="primary",
                icon=":material/travel_explore:", disabled=not sectors)

if run and dry:
    p = PF.plan(sectors, country, mode)
    p["strict_filters"] = strict and mode == "serper"
    st.session_state["finder_plan"] = p
    st.session_state.pop("finder_result", None)
elif run:
    st.session_state.pop("finder_plan", None)
    budget = PF.Budget()
    bar = st.progress(0.0, text="0/%d sectors" % len(sectors))
    log_box = st.empty()
    log = []

    def on_log(msg):
        log.append(msg)
        log_box.markdown(C.code_block("\n".join(log[-10:]), "live log"),
                         unsafe_allow_html=True)

    runs, merged, warnings = [], [], []
    with st.spinner("Finding prospects…"):
        for i, s in enumerate(sectors):
            on_log("[%d/%d] %s → searching (%s)…" % (i + 1, len(sectors), s,
                                                     mode))
            extra = {"budget": budget} if mode == "serper" else {}
            extra["strict_filters"] = strict
            r = PF.find_prospects(s, country, int(max_n), mode,
                                  progress_callback=on_log, **extra)
            runs.append(r)
            merged += r["companies"]
            warnings += ["%s: %s" % (s, w) for w in r["warnings"]]
            on_log("[%d/%d] %s → %d found, %d with email, %d rejected" % (
                i + 1, len(sectors), s, r["companies_found"],
                r["companies_with_email"], r["companies_rejected"]["total"]))
            bar.progress((i + 1) / len(sectors),
                         text="%d/%d sectors" % (i + 1, len(sectors)))
    merged = PF.dedupe_companies(merged)
    res = {"mode": mode, "country": country, "sectors": sectors,
           "companies": merged, "warnings": warnings,
           "serper_calls": sum(r["serper_calls"] for r in runs),
           "pages_fetched": sum(r["pages_fetched"] for r in runs),
           "strict_filters": strict and mode == "serper",
           **PF.merge_filter_stats(runs),
           "out_path": None}
    if save:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        res["out_path"] = PF._write(PF.DEFAULT_OUT_DIR /
                                    ("finder_%s.json" % ts), res)
    st.session_state["finder_result"] = res

plan = st.session_state.get("finder_plan")
if plan:
    C.render(st, C.section_header("Dry run plan",
                                  "Nothing was fetched and no Serper call "
                                  "was made."))
    C.render(st, C.kpi_grid([
        {"label": "Sectors", "value": len(plan["sectors"]),
         "icon_svg": ICONS["list"]},
        {"label": "Serper calls planned", "value":
         plan["serper_calls_planned"], "icon_svg": ICONS["search"],
         "delta": "cap %d per run" % PF.MAX_SERPER_CALLS_PER_RUN},
        {"label": "Page fetch cap", "value": plan["page_fetch_cap"],
         "icon_svg": ICONS["globe"]},
    ], columns=3))
    filtering_report(PF.empty_filter_stats(), plan.get("strict_filters"),
                     "Dry run: nothing was fetched, so nothing was filtered "
                     "yet. On a real run every result passes the six "
                     "filters and the counts appear here.")
    for step in plan["steps"]:
        with st.expander(step["sector"]):
            if "queries" in step:
                st.code("\n".join(step["queries"]))
            else:
                for d in step["directories"]:
                    st.write("**%s** — %s" % (d["directory"], "enabled"
                                              if d["enabled"] else
                                              "disabled: %s" % d["reason"]))
                    if d["urls"]:
                        st.code("\n".join(d["urls"]))

res = st.session_state.get("finder_result")
if res:
    comps = res["companies"]
    C.render(st, C.section_header(
        "Results", "Saved to %s" % res["out_path"] if res["out_path"]
        else "Not saved to a file"))
    C.render(st, C.kpi_grid([
        {"label": "Companies found", "value": len(comps),
         "icon_svg": ICONS["users"]},
        {"label": "With email", "value": sum(1 for c in comps
                                             if c.get("email")),
         "icon_svg": ICONS["send"]},
        {"label": "With phone", "value": sum(1 for c in comps
                                             if c.get("phone_e164")),
         "icon_svg": ICONS["activity"]},
        {"label": "Serper calls made", "value": res["serper_calls"],
         "icon_svg": ICONS["search"]},
        {"label": "Pages fetched", "value": res["pages_fetched"],
         "icon_svg": ICONS["globe"]},
    ], columns=5))
    filtering_report(res, res.get("strict_filters"))
    if comps:
        st.dataframe(pd.DataFrame([{
            "company": c.get("company_name"), "email": c.get("email") or "",
            "phone": c.get("phone_e164") or "",
            "website": c.get("website") or "", "sector": c.get("sector"),
            "country": c.get("country"), "source": c.get("source"),
            "confidence": c.get("confidence")} for c in comps]),
            width="stretch", hide_index=True)
        st.download_button("Download JSON",
                           json.dumps(res, ensure_ascii=False,
                                      indent=1).encode("utf-8"),
                           file_name=Path(res["out_path"]).name
                           if res["out_path"] else "finder.json",
                           mime="application/json",
                           icon=":material/download:")
    else:
        C.render(st, C.empty_state("No prospects found",
                                   "See the warnings below for why.",
                                   ICONS["search"]))
    if res["warnings"]:
        with st.expander("Warnings (%d)" % len(res["warnings"])):
            st.code("\n".join(res["warnings"]))
    C.render(st, C.status_pill(
        "Import to Queue is not available yet: the outreach importer reads "
        "Instant Data Scraper CSVs. Download and review first.", "info"))

# ── safety ──
C.render(st, C.section_header("Safety"))
b1, b2 = st.columns([1, 3])
if b1.button("Check Serper balance", icon=":material/account_balance:"):
    bal = PF.serper_balance()
    st.session_state["serper_balance"] = bal
bal = st.session_state.get("serper_balance")
balance_text = ("Current balance: %s" % bal.get("balance")
                if bal and bal.get("ok") and bal.get("balance") is not None
                else "check serper.dev for the current balance")
C.render(st, C.glass_card("Before you run", (
    "Serper calls are billed — %s. A full run is at most %d calls.<br>"
    "Playwright respects robots.txt and adds delays between pages.<br>"
    "No stealth, no proxies, no captcha solving.") % (
        balance_text, PF.MAX_SERPER_CALLS_PER_RUN), accent="indigo"))
