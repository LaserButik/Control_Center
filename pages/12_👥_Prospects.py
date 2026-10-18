# -*- coding: utf-8 -*-
"""Browse the prospects of a run: filter by country, industry, tier and
mobile, sort by score, export CSV. Read-only — no data file is changed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import charts, components as C
from ui.icons import ICONS
from ui.i18n import t, get_lang
from connectors import outreach

lang = get_lang()
page_config(st, t("prospects.page_title", lang))
render_sidebar(st)

page_header(st, t("prospects.title", lang), "", "users")

runs = outreach.list_runs()
if not runs:
    C.render(st, C.empty_state(t("common.nothing_yet", lang),
                               t("prospects.no_runs", lang), ICONS["inbox"]))
    st.stop()

run_id = st.selectbox(t("common.run", lang), [r["run_id"] for r in runs])
pros = outreach.load_run(run_id).get("prospects", [])
if not pros:
    C.render(st, C.empty_state(t("common.nothing_yet", lang),
                               t("prospects.none_in_run", lang),
                               ICONS["inbox"]))
    st.stop()

# internal column -> visible header (the CSV export keeps the internal names)
COLS = {c: t("prospects.col_" + c, lang) for c in
        ("company", "phone", "country", "industry", "tier", "score",
         "has_mobile", "skipped", "skip_reason")}

df = pd.DataFrame([{
    "company": p.get("company_name"),
    "phone": p.get("phone_e164") or p.get("phone"),
    "country": p.get("country") or "—",
    "industry": (p.get("industry") or "—")[:40],
    "tier": p.get("tier") or "—",
    "score": p.get("score"),
    "has_mobile": bool(p.get("phone_e164")),
    "skipped": p.get("skipped", False),
    "skip_reason": p.get("csv_skip_reason") or "",
} for p in pros])

f = st.columns(4)
countries = f[0].multiselect(COLS["country"], sorted(df["country"].unique()))
tiers = f[1].multiselect(COLS["tier"], sorted(df["tier"].unique()))
industry = f[2].text_input(t("prospects.industry_contains", lang))
mobile_only = f[3].checkbox(t("prospects.mobile_only", lang))

view = df.copy()
if countries:
    view = view[view["country"].isin(countries)]
if tiers:
    view = view[view["tier"].isin(tiers)]
if industry:
    view = view[view["industry"].str.lower().str.contains(industry.lower(),
                                                           na=False)]
if mobile_only:
    view = view[view["has_mobile"]]

view = view.sort_values("score", ascending=False, na_position="last")

c = st.columns(3)
c[0].metric(t("prospects.total", lang), len(df))
c[1].metric(t("common.shown", lang), len(view))
c[2].metric(t("prospects.with_mobile", lang), int(df["has_mobile"].sum()))

scores = pd.to_numeric(view["score"], errors="coerce").dropna()
if not scores.empty:
    charts.show(st, charts.histogram(scores.tolist(),
                                     title=t("prospects.score_chart", lang)),
                empty_title=t("common.chart_unavailable", lang))

st.dataframe(view.rename(columns=COLS), width="stretch", hide_index=True)
st.download_button(t("common.export_csv", lang),
                   view.to_csv(index=False).encode("utf-8"),
                   icon=":material/download:",
                   file_name="prospects_%s.csv" % run_id, mime="text/csv")
