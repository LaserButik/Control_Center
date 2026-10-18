# -*- coding: utf-8 -*-
"""Outreach Reports — the daily run's reports: every day's numbers, 30-day
trends, email vs WhatsApp, per sector, and exports. Read-only.
(Named Outreach_Reports because /Reports is the PDF report page.)
"""

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: F401,E402  (loads .env first)

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar, page_header
from ui import charts as CH
from ui import components as C
from ui.icons import ICONS
from atlas_services import email_tracker as ET
from atlas_services import telegram_reporter as TG
from atlas_services import whatsapp_tracker as WT

page_config(st, "Outreach Reports")
render_sidebar(st)

page_header(st, "Outreach reports",
            "What the daily run sent, what came back, and how each channel "
            "and sector is doing.", "chart")

REPORTS = ROOT / "data" / "reports"


def load_reports(include_dry: bool) -> list[dict]:
    out = []
    for f in sorted(REPORTS.glob("daily_*.json")) if REPORTS.is_dir() else []:
        if f.stem.endswith("_dryrun") and not include_dry:
            continue
        try:
            rep = json.loads(f.read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            continue
        rep["_file"] = f.name
        out.append(rep)
    return out[-30:]


def g(rep, *keys):
    for k in keys:
        rep = (rep or {}).get(k) if isinstance(rep, dict) else None
    return rep or 0


include_dry = st.toggle("Include dry runs", value=False)
reports = load_reports(include_dry)
rows = [{"date": r.get("date"), "mode": r.get("mode", "real"),
         "found": g(r, "prospects", "found"), "new": g(r, "prospects", "new"),
         "email sent": g(r, "email", "sent"),
         "WhatsApp sent": g(r, "whatsapp", "sent"),
         "follow-ups": g(r, "combined", "followups_sent"),
         "replies": g(r, "combined", "replies"),
         "bounces": g(r, "combined", "bounces"),
         "unsubscribes": g(r, "combined", "unsubscribes"),
         "file": r["_file"]} for r in reports]

# ── 1. daily ──
C.render(st, C.section_header("1 · Daily reports", "The last 30 days, "
                              "newest first."))
if rows:
    st.dataframe(pd.DataFrame(list(reversed(rows))), width="stretch",
                 hide_index=True)
    pick = st.selectbox("Open a day", [r["file"] for r in reversed(rows)])
    chosen = next(r for r in reports if r["_file"] == pick)
    a, b = st.columns(2)
    with a:
        st.caption("As sent to Telegram")
        st.code(TG.format_daily_report(chosen))
    with b:
        st.caption("Full report")
        st.json({k: v for k, v in chosen.items() if k != "_file"},
                expanded=False)
else:
    chosen = None
    C.render(st, C.empty_state("No reports yet",
                               "The daily run writes one report per day to "
                               "data/reports/.", ICONS["chart"]))

# ── 2. weekly ──
C.render(st, C.section_header("2 · Trends", "Last 30 days."))
if rows:
    dates = [r["date"] for r in rows]
    sent = [r["email sent"] + r["WhatsApp sent"] for r in rows]
    replies = [r["replies"] for r in rows]
    total_sent, total_replies = sum(sent), sum(replies)
    C.render(st, C.kpi_grid([
        {"label": "Total sent", "value": total_sent,
         "icon_svg": ICONS["send"]},
        {"label": "Total replies", "value": total_replies,
         "icon_svg": ICONS["inbox"]},
        {"label": "Reply rate", "value": "%.1f%%" % (
            100.0 * total_replies / total_sent if total_sent else 0.0),
         "icon_svg": ICONS["trend_up"]},
        {"label": "Days reported", "value": len(rows),
         "icon_svg": ICONS["calendar"]},
    ], columns=4))
    c1, c2 = st.columns(2)
    with c1:
        CH.show(st, CH.line(dates, [r["email sent"] for r in rows],
                            title="Emails sent per day"))
    with c2:
        CH.show(st, CH.line(dates, replies, title="Replies per day"))
else:
    C.render(st, C.status_pill("Trends appear after the first real run.",
                               "neutral"))

# ── 3. channels ──
C.render(st, C.section_header("3 · Channels", "All time, from the send "
                              "logs and prospect states."))
e_log, w_log = ET.read_sent_log(), WT.read_sent_log()
e_states = ET.EmailTracker().all_states()
w_states = WT.WhatsAppTracker().all_states()
st.dataframe(pd.DataFrame([
    {"channel": "Email",
     "sent": sum(r.get("status") == "sent" for r in e_log),
     "delivered": None,                 # email has no delivery receipts
     "opened / read": sum(s.get("opens", 0) for s in e_states),
     "replies": sum(s.get("replies", 0) for s in e_states),
     "bounced": sum(s.get("status") == "bounced" for s in e_states),
     "unsubscribed": sum(s.get("status") == "unsubscribed"
                         for s in e_states)},
    {"channel": "WhatsApp",
     "sent": sum(r.get("status") == "sent" for r in w_log),
     "delivered": sum(s.get("delivered", 0) for s in w_states),
     "opened / read": sum(s.get("read", 0) for s in w_states),
     "replies": sum(s.get("replies", 0) for s in w_states),
     "bounced": sum(s.get("status") == "bounced" for s in w_states),
     "unsubscribed": sum(s.get("status") == "unsubscribed"
                         for s in w_states)},
]), width="stretch", hide_index=True)
sectors = {}
for channel, log_rows, states in (("email", e_log, e_states),
                                  ("whatsapp", w_log, w_states)):
    for r in log_rows:
        if r.get("status") == "sent":
            s = sectors.setdefault(r.get("sector") or "unknown",
                                   {"email sent": 0, "WhatsApp sent": 0,
                                    "replies": 0})
            s["email sent" if channel == "email" else "WhatsApp sent"] += 1
    for st_ in states:
        if st_.get("replies"):
            sectors.setdefault(st_.get("sector") or "unknown",
                               {"email sent": 0, "WhatsApp sent": 0,
                                "replies": 0})["replies"] += st_["replies"]
if sectors:
    C.render(st, C.section_header("Per sector"))
    st.dataframe(pd.DataFrame([dict(sector=k, **v) for k, v in
                               sorted(sectors.items())]), width="stretch",
                 hide_index=True)
    CH.show(st, CH.bars(list(sectors), [v["email sent"] + v["WhatsApp sent"]
                                        for v in sectors.values()],
                        title="Messages sent per sector"))
else:
    C.render(st, C.status_pill("No sends yet.", "neutral"))

# ── 4. export ──
C.render(st, C.section_header("4 · Export"))
x1, x2 = st.columns(2)
if chosen:
    x1.download_button("Download %s (JSON)" % chosen["_file"],
                       json.dumps({k: v for k, v in chosen.items()
                                   if k != "_file"}, ensure_ascii=False,
                                  indent=1).encode("utf-8"),
                       file_name=chosen["_file"], mime="application/json",
                       icon=":material/download:", key="dl_report_json")
buf = io.StringIO()
if rows:
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
x2.download_button("Download all days (CSV)",
                   buf.getvalue().encode("utf-8-sig"),
                   file_name="outreach_daily_reports.csv", mime="text/csv",
                   icon=":material/download:", disabled=not rows,
                   key="dl_reports_csv")
