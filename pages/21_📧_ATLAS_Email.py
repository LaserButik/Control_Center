# -*- coding: utf-8 -*-
"""ATLAS --- Email Engine: four tabs (Templates, Compose, Follow-ups, History)."""

import csv
import html
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ui_common import page_config, render_sidebar, page_header
from ui import components as C
from ui.icons import ICONS
from ui.i18n import t, get_lang
from atlas_services import email_templates as T
from atlas_services import email_sender as ES
from atlas_services import email_tracker as ET
from atlas_services.email_sequence import EmailSequence

page_config(st, "ATLAS Email")
render_sidebar(st)

lang = get_lang()
page_header(st, t("email.title", lang), t("email.subtitle", lang), "send")

PROSPECTS_DIR = Path(__file__).resolve().parent.parent / "data" / "prospects"
SECTOR_LABELS = {"clinics": "Clinics", "real_estate": "Real estate",
                 "restaurants": "Restaurants", "salons": "Salons",
                 "lawyers": "Lawyers"}
MODES = [t("email.dry_run", lang), t("email.real_send", lang)]

tracker = ET.EmailTracker()


def new_sender(real: bool) -> ES.EmailSender:
    return ES.EmailSender(dry_run=not real, tracker=tracker)


probe = new_sender(False)
sent_today_count, limit = probe.sent_today(), probe.daily_limit

if not probe.is_configured():
    st.warning(t("email.smtp_not_configured", lang))


def text_block(text: str, rtl: bool) -> str:
    return ("<div dir='%s' style='white-space:normal;background:rgba(15,20,25,"
            "0.6);border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
            "padding:14px 16px;font-size:14px;line-height:1.7;color:#C9D1E0;"
            "text-align:%s;'>%s</div>"
            % ("rtl" if rtl else "ltr", "right" if rtl else "left",
               html.escape(text).replace("\n", "<br>")))


def show_email(rendered: dict, rtl: bool, key: str) -> None:
    C.render(st, text_block(rendered["subject"], rtl))
    with st.expander("HTML", expanded=False):
        components.html(rendered["body_html"], height=500, scrolling=True)


def mode_controls(key: str):
    m1, m2 = st.columns([1, 2])
    mode = m1.radio("Mode", MODES, key="mode_" + key)
    real = mode == MODES[1]
    confirmed = m2.checkbox(t("email.confirm_send", lang),
                            value=False, disabled=not real,
                            key="confirm_" + key)
    return real, real and confirmed


# -- four tabs --
tab_templates, tab_compose, tab_followups, tab_history = st.tabs([
    t("email.tab_templates", lang),
    t("email.tab_compose", lang),
    t("email.tab_followups", lang),
    t("email.tab_history", lang),
])

# ---- TAB 1: Templates (read-only preview) ----
with tab_templates:
    _sectors = list(SECTOR_LABELS.keys())
    _tpl_sector = st.selectbox("Sector", _sectors,
                               format_func=lambda s: SECTOR_LABELS.get(s, s),
                               key="tpl_sector")
    _tpl_lang = st.radio("Language", ["ar", "en"], horizontal=True,
                         key="tpl_lang")
    _tpls = T.get_templates(_tpl_sector, _tpl_lang)
    _day0 = [tp for tp in _tpls if tp["day"] == "day0"]
    _day3 = [tp for tp in _tpls if tp["day"] == "day3"]
    _sample = {"company_name": "Acme Corp", "contact_name": "Ahmed"}
    _d0_tab, _d3_tab = st.tabs(["Day 0", "Day 3"])
    for _sub, _items in [(_d0_tab, _day0), (_d3_tab, _day3)]:
        with _sub:
            for _tp in _items:
                _rendered = T.render(_tp, _sample)
                _rtl = _tpl_lang == "ar"
                st.markdown("**Subject:** %s" % html.escape(
                    _rendered["subject"]))
                C.render(st, text_block(_rendered["body"], _rtl))
                with st.expander("HTML preview", expanded=False):
                    components.html(_rendered["body_html"], height=500,
                                    scrolling=True)
    C.render(st, C.section_header("All 20 templates"))
    _all_rows = []
    for _tid in T.list_all_template_ids():
        _tp = T.get_template_by_id(_tid)
        if _tp:
            _all_rows.append({"ID": _tp["id"], "Sector": _tp["sector"],
                              "Language": _tp["language"], "Day": _tp["day"],
                              "Subject": _tp["subject"]})
    st.dataframe(pd.DataFrame(_all_rows), width="stretch", hide_index=True)

# ---- TAB 2: Compose ----
with tab_compose:
    def load_companies(raw) -> list[dict]:
        data = raw.get("companies", []) if isinstance(raw, dict) else raw
        return [c for c in (data or []) if isinstance(c, dict)]

    files = sorted(PROSPECTS_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True) \
        if PROSPECTS_DIR.exists() else []

    picked = st.selectbox(t("email.select_file", lang),
                          ["---"] + [p.name for p in files], key="pf_file")
    upload = st.file_uploader("JSON", type=["json"], key="pf_upload",
                              label_visibility="collapsed")
    companies, source = [], None
    try:
        if upload is not None:
            companies, source = load_companies(json.loads(
                upload.getvalue().decode("utf-8"))), upload.name
        elif picked != "---":
            companies, source = load_companies(json.loads(
                (PROSPECTS_DIR / picked).read_bytes().decode("utf-8"))), picked
    except ValueError as e:
        st.error("Invalid JSON: %s" % e)

    with_email = [c for c in companies if ET.normalize_email(c.get("email"))]
    send_lang = st.radio("Language", ["ar", "en"], horizontal=True,
                         key="send_lang")
    if source and with_email:
        st.dataframe(pd.DataFrame([{
            "company": c.get("company_name"), "email": c.get("email")}
            for c in with_email[:50]]), width="stretch", hide_index=True)

    remaining = max(0, limit - sent_today_count)
    if with_email:
        st.caption(t("email.ready_status", lang)
                   .replace("{n}", str(len(with_email)))
                   .replace("{remaining}", str(remaining)))

    real0, confirmed0 = mode_controls("day0")
    go0 = st.button(t("email.send_day0", lang), type="primary",
                    icon=":material/send:",
                    disabled=not with_email or (real0 and not confirmed0),
                    key="btn_day0")
    if go0:
        sender = new_sender(real0)
        seq = EmailSequence(sender, tracker)
        rows = []
        bar = st.progress(0.0, text="0/%d" % len(with_email))
        for i, c in enumerate(with_email):
            out = seq.start(c, language=send_lang, confirmed=confirmed0)
            r = out["result"]
            rows.append({"company": c.get("company_name"),
                         "email": r["email"],
                         "status": r["status"],
                         "reason": r["reason"] or ""})
            bar.progress((i + 1) / len(with_email),
                         text="%d/%d" % (i + 1, len(with_email)))
        st.session_state["day0_rows"] = rows
        st.rerun()
    if st.session_state.get("day0_rows"):
        rows = st.session_state["day0_rows"]
        counts = pd.Series([r["status"] for r in rows]).value_counts().to_dict()
        C.render(st, C.status_pill("Last run: " + ", ".join(
            "%s %d" % kv for kv in counts.items()), "info"))
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ---- TAB 3: Follow-ups ----
with tab_followups:
    due = tracker.get_due_followups()
    if due:
        st.dataframe(pd.DataFrame([{
            "company": d.get("company_name"), "email": d["email"],
            "sector": d.get("sector"),
            "day 0 sent": d.get("last_sent_at")}
            for d in due]), width="stretch", hide_index=True)
    else:
        C.render(st, C.empty_state(t("email.no_followups", lang),
                                   "", ICONS["clock"]))
    real3, confirmed3 = mode_controls("day3")
    go3 = st.button(t("email.send_followups", lang),
                    icon=":material/schedule_send:",
                    disabled=not due or (real3 and not confirmed3),
                    key="btn_day3")
    if go3:
        summary = EmailSequence(new_sender(real3),
                                tracker).process_due_followups(
            language_pref=None, confirmed=confirmed3)
        st.session_state["day3_summary"] = summary
        st.rerun()
    summary = st.session_state.get("day3_summary")
    if summary:
        C.render(st, C.status_pill(
            "%(due)d due / %(sent)d sent / %(blocked)d blocked" % summary,
            "info"))

# ---- TAB 4: History ----
with tab_history:
    C.render(st, C.section_header(t("email.last_sends", lang)))
    log_rows = ET.read_sent_log()
    if log_rows:
        st.dataframe(pd.DataFrame([{
            "at": r.get("at"), "email": r.get("email"),
            "company": r.get("company_name"),
            "status": r.get("status"),
            "reason": r.get("reason") or ""}
            for r in reversed(log_rows[-30:])]),
            width="stretch", hide_index=True)
    else:
        C.render(st, C.empty_state("No sends yet", "", ICONS["inbox"]))

    C.render(st, C.section_header(t("email.suppression", lang)))
    entries = ET.suppression_entries()
    if entries:
        st.dataframe(pd.DataFrame([{"email": e, "reason": v.get("reason"),
                                    "added": v.get("at")}
                                   for e, v in sorted(entries.items())]),
                     width="stretch", hide_index=True)
    with st.form("add_suppression"):
        a1, a2 = st.columns([2, 2])
        sup_email = a1.text_input("Email")
        sup_reason = a2.text_input("Reason", "manual")
        if st.form_submit_button("Add"):
            res = ES.add_to_suppression(sup_email, sup_reason or "manual")
            if res["ok"]:
                st.success("%s added" % res["email"])
            else:
                st.error("Enter a valid email address.")

    with st.form("record_event"):
        e1, e2, e3 = st.columns([2, 1, 2])
        ev_email = e1.text_input("Email", key="ev_email")
        ev_kind = e2.selectbox("Event", ["replied", "bounced",
                                         "unsubscribed"])
        ev_note = e3.text_input("Note", key="ev_note")
        if st.form_submit_button(t("email.record_event", lang)):
            fn = {"replied": lambda: tracker.record_replied(ev_email, ev_note),
                  "bounced": lambda: tracker.record_bounced(ev_email, ev_note),
                  "unsubscribed": lambda: tracker.record_unsubscribed(
                      ev_email, ev_note or "manual")}
            res = fn[ev_kind]()
            if res.get("email"):
                st.success("Recorded %s for %s" % (ev_kind, res["email"]))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "reason", "added"])
    for e, v in sorted(entries.items()):
        w.writerow([e, v.get("reason", ""), v.get("at", "")])
    st.download_button("Export CSV", buf.getvalue().encode("utf-8-sig"),
                       file_name="suppression.csv", mime="text/csv",
                       icon=":material/download:", key="dl_suppression")
