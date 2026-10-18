# -*- coding: utf-8 -*-
"""Pick a run and approve or reject its queued messages. Filter by status,
language and tier, search by company or phone, sort, and bulk-decide."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar, show_result
from ui_common import page_header, status_label
from ui import components as C
from ui.icons import ICONS
from ui.i18n import t, get_lang
from connectors import outreach

lang = get_lang()
page_config(st, t("queue.page_title", lang))
render_sidebar(st)

page_header(st, t("queue.title", lang), "", "list")
st.caption(t("queue.caption", lang))

runs = [r for r in outreach.list_runs() if r["has_queue"]]
if not runs:
    C.render(st, C.empty_state(t("common.nothing_yet", lang),
                               t("common.no_queue_runs", lang),
                               ICONS["inbox"]))
    st.stop()

run_id = st.selectbox(t("common.run", lang), [r["run_id"] for r in runs])
data = outreach.load_run(run_id)
entries = data.get("entries", [])
prospects = {p.get("id"): p for p in data.get("prospects", [])}

# internal column -> visible header
COLS = {c: t("queue.col_" + c, lang) for c in
        ("queue_id", "status", "language", "tier", "company", "to",
         "subject")}
LANGS = {"ar": t("common.lang_ar", lang), "en": t("common.lang_en", lang)}


def tier_of(e):
    return (prospects.get(e.get("prospect_id")) or {}).get("tier") or "—"


rows = [{"queue_id": e.get("queue_id", ""),
         "status": e.get("status"), "language": e.get("language") or "—",
         "tier": tier_of(e), "company": (prospects.get(e.get("prospect_id"))
                                         or {}).get("company_name") or "—",
         "to": e.get("prospect_email"),
         "subject": (e.get("subject") or "")[:70]} for e in entries]
df = pd.DataFrame(rows, columns=list(COLS))

# ── filters ──
f = st.columns(4)
statuses = f[0].multiselect(COLS["status"],
                            sorted(df["status"].dropna().unique()),
                            default=["pending"] if "pending" in
                            df["status"].values else [],
                            format_func=lambda s: status_label(s, lang))
langs = f[1].multiselect(COLS["language"], sorted(df["language"].unique()),
                         format_func=lambda v: LANGS.get(v, v))
tiers = f[2].multiselect(COLS["tier"], sorted(df["tier"].unique()))
search = f[3].text_input(t("queue.search", lang))

view = df.copy()
if statuses:
    view = view[view["status"].isin(statuses)]
if langs:
    view = view[view["language"].isin(langs)]
if tiers:
    view = view[view["tier"].isin(tiers)]
if search:
    s = search.lower()
    view = view[view["company"].str.lower().str.contains(s, na=False)
                | view["to"].astype(str).str.lower().str.contains(s,
                                                                  na=False)]

sort_col = st.selectbox(t("queue.sort_by", lang), list(df.columns), index=1,
                        format_func=lambda c: COLS.get(c, c))
view = view.sort_values(sort_col)

c = st.columns(4)
c[0].metric(t("queue.total", lang), len(df))
c[1].metric(t("common.shown", lang), len(view))
c[2].metric(t("queue.pending_all", lang),
            int((df["status"] == "pending").sum()))
c[3].metric(t("queue.approved_all", lang),
            int((df["status"] == "approved").sum()))

st.dataframe(view.assign(
    queue_id=view["queue_id"].str[:8],
    status=view["status"].map(lambda s: status_label(s, lang)),
    language=view["language"].map(lambda v: LANGS.get(v, v)))
    .rename(columns=COLS), width="stretch", hide_index=True)

# ── bulk decide (pending only within the current view) ──
st.divider()
C.render(st, C.section_header(t("queue.bulk", lang)))
pending_ids = view[view["status"] == "pending"]["queue_id"].tolist()
if not pending_ids:
    st.info(t("queue.no_pending", lang))
else:
    chosen = st.multiselect(
        t("queue.entries", lang), pending_ids,
        format_func=lambda q: "%s · %s" % (q[:8], df.loc[
            df["queue_id"] == q, "company"].iloc[0]))
    by = st.text_input(t("queue.reviewer", lang), value="control_center")
    reason = st.text_input(t("queue.reject_reason", lang),
                           value=t("queue.reason_default", lang))
    a, b = st.columns(2)
    if a.button(t("queue.approve", lang), type="primary",
                icon=":material/check:", disabled=not chosen):
        for q in chosen:
            with st.spinner(t("queue.approving", lang).replace("{id}",
                                                               q[:8])):
                show_result(st, outreach.approve_queue_entry(run_id, q, by))
    if b.button(t("queue.reject", lang), icon=":material/close:",
                disabled=not chosen):
        for q in chosen:
            with st.spinner(t("queue.rejecting", lang).replace("{id}",
                                                               q[:8])):
                show_result(st, outreach.reject_queue_entry(run_id, q, by,
                                                            reason))
