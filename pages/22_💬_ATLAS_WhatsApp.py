# -*- coding: utf-8 -*-
"""ATLAS — WhatsApp Engine: the 20 sector templates (plus two day 7
nudges), Meta submission payloads, day 0 and day 2 sends, status and the
suppression list. Dry run is the default everywhere; a real send needs
"Real send" AND the confirm checkbox. Nothing is ever submitted to Meta
from here.
"""

import csv
import html
import io
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402  (loads .env first)

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar, page_header
from ui import components as C
from ui.icons import ICONS
from atlas_services import email_tracker as ET
from atlas_services import whatsapp_sender as WS
from atlas_services import whatsapp_templates as W
from atlas_services import whatsapp_tracker as WT

page_config(st, "ATLAS WhatsApp")
render_sidebar(st)

page_header(st, "ATLAS — WhatsApp Engine",
            "Meta-ready templates in Arabic and English, gated sending "
            "through the Cloud API, delivery and reply tracking.", "send")

PROSPECTS_DIR = Path(__file__).resolve().parent.parent / "data" / "prospects"
SECTOR_LABELS = {"clinics": "Clinics", "real_estate": "Real estate",
                 "restaurants": "Restaurants", "salons": "Salons",
                 "lawyers": "Lawyers"}
MODES = ["Dry run (nothing is sent)", "Real send"]

tracker = WT.WhatsAppTracker()


def new_sender(real: bool) -> WS.WhatsAppSender:
    return WS.WhatsAppSender(dry_run=not real, tracker=tracker)


probe = new_sender(False)
sent_today, limit = probe.sent_today(), probe.daily_limit
cfg = probe.config_summary()


def limit_bar() -> None:
    left = max(0, limit - sent_today)
    C.render(st, "<div>%s%s%s</div>" % (
        C.status_pill("Daily limit: %d / %d sent today · %d remaining"
                      % (sent_today, limit, left),
                      "success" if left else "danger"),
        C.status_pill("Meta credentials set" if probe.is_configured() else
                      "Meta not configured (WHATSAPP_PHONE_ID, "
                      "WHATSAPP_TOKEN)",
                      "success" if probe.is_configured() else "warning"),
        C.status_pill("Approved: %s" % (", ".join(cfg["approved_templates"])
                                        or "none"), "info")))


def text_block(text: str, rtl: bool) -> str:
    return ("<div dir='%s' style='white-space:normal;background:rgba(8,9,12,"
            "0.6);border:1px solid rgba(255,255,255,0.08);border-radius:12px;"
            "padding:14px 16px;font-size:14.5px;line-height:1.7;"
            "color:#C9D1E0;text-align:%s;max-width:560px;'>%s</div>"
            % ("rtl" if rtl else "ltr", "right" if rtl else "left",
               html.escape(text).replace("\n", "<br>")))


def mode_controls(key: str):
    m1, m2 = st.columns([1, 2])
    mode = m1.radio("Mode", MODES, key="wa_mode_" + key)
    real = mode == MODES[1]
    confirmed = m2.checkbox("I confirm: send real WhatsApp messages now",
                            value=False, disabled=not real,
                            key="wa_confirm_" + key)
    if real and not confirmed:
        C.render(st, C.status_pill("Real send selected: tick the confirm "
                                   "box to enable sending.", "warning"))
    return real, real and confirmed


limit_bar()

# ── 1. templates ──
C.render(st, C.section_header(
    "1 · Templates", "%d templates: 5 sectors × Arabic and English × day 0 "
    "and day 2, plus a day 7 nudge per language" % len(W.list_all_ids())))
t1, t2, t3 = st.columns([2, 1, 3])
sector = t1.selectbox("Sector", list(W.TEMPLATES),
                      format_func=SECTOR_LABELS.get, key="wa_tpl_sector")
lang = t2.radio("Language", ["ar", "en"], horizontal=True, key="wa_tpl_lang")
sample = {"company_name": t3.text_input("Sample company",
                                        "Smile Dental Clinic",
                                        key="wa_sample"), "sector": sector}
for tab, tpl in zip(st.tabs(["Day 0 · first message", "Day 2 · follow-up"]),
                    W.get_sequence(sector, lang)):
    with tab:
        probs = W.problems(tpl)
        C.render(st, "<div>%s%s%s</div>" % (
            C.status_pill("Meta name: %s" % tpl["name"], "neutral"),
            C.status_pill("%d / %d characters" % (len(tpl["body"]),
                                                  W.MAX_CHARS),
                          "success" if len(tpl["body"]) <= W.MAX_CHARS
                          else "danger"),
            C.status_pill("Approved on Meta" if tpl["name"] in
                          cfg["approved_templates"] else "Not approved yet",
                          "success" if tpl["name"] in cfg[
                              "approved_templates"] else "warning")))
        C.render(st, text_block(W.preview_text(tpl, sample), lang == "ar"))
        if probs:
            st.error("Rule problems: %s" % ", ".join(probs))
        if st.button("Submit to Meta (show payload)", key="pl_" + tpl["id"],
                     icon=":material/data_object:"):
            st.session_state["wa_payload"] = tpl["id"]
        if st.session_state.get("wa_payload") == tpl["id"]:
            st.caption("Not submitted. Create the template in Meta Business "
                       "Suite → WhatsApp Manager → Message templates with "
                       "exactly these values, or POST it to "
                       "/{WABA_ID}/message_templates yourself.")
            st.code(json.dumps(next(p for p in W.export_for_meta_submission()
                                    if p["name"] == tpl["name"]),
                               ensure_ascii=False, indent=2), language="json")
with st.expander("All templates (%d + %d nudges)" % (
        len(W.list_all_ids()), len(W.LATE_TEMPLATES))):
    st.dataframe(pd.DataFrame([{
        "id": t["id"], "Meta name": t["name"], "language": t["language"],
        "step": t["category"], "chars": len(t["body"]),
        "approved": t["name"] in cfg["approved_templates"],
        "body": t["body"]} for t in W.all_templates()]),
        width="stretch", hide_index=True)
    st.download_button("Download all Meta payloads (JSON)", json.dumps(
        W.export_for_meta_submission(), ensure_ascii=False, indent=1)
        .encode("utf-8"), file_name="whatsapp_templates_for_meta.json",
        mime="application/json", icon=":material/download:",
        key="dl_meta_payloads")
if cfg["day0_fallback"]:
    st.caption("Until a day 0 template is approved, day 0 goes out as the "
               "approved %s (company name + industry)."
               % cfg["day0_fallback"])

# ── 2. send day 0 ──
C.render(st, C.section_header("2 · Send day 0 to prospects",
                              "Only UAE (+9715…) and Saudi (+9665…) mobile "
                              "numbers are kept."))


def load_companies(raw) -> list[dict]:
    data = raw.get("companies", []) if isinstance(raw, dict) else raw
    return [c for c in (data or []) if isinstance(c, dict)]


files = sorted(PROSPECTS_DIR.glob("*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True) \
    if PROSPECTS_DIR.exists() else []
s1, s2 = st.columns(2)
picked = s1.selectbox("Prospects file (data/prospects/)",
                      ["—"] + [p.name for p in files], key="wa_file")
upload = s2.file_uploader("…or upload a JSON file", type=["json"],
                          key="wa_upload")
companies, source = [], None
try:
    if upload is not None:
        companies, source = load_companies(json.loads(
            upload.getvalue().decode("utf-8"))), upload.name
    elif picked != "—":
        companies, source = load_companies(json.loads(
            (PROSPECTS_DIR / picked).read_bytes().decode("utf-8"))), picked
except ValueError as e:
    st.error("That file is not valid JSON: %s" % e)

mobiles = [c for c in companies if WS.is_mobile(c.get("phone_e164")
                                                or c.get("phone"))]
send_lang = st.radio("Language for day 0", ["ar", "en"], horizontal=True,
                     key="wa_send_lang")
real0, confirmed0 = mode_controls("day0")
seq_probe = WS.WhatsAppSequence(probe, tracker)
if source:
    sup = WS.load_suppression()
    C.render(st, C.status_pill("%s · %d companies · %d with an AE/SA mobile"
                               % (source, len(companies), len(mobiles)),
                               "info"))
    if mobiles:
        rows = []
        for c in mobiles:
            ph = WT.normalize_phone(c.get("phone_e164") or c.get("phone"))
            pv = seq_probe.preview(c, day="day0", language=send_lang)
            rows.append({"company": c.get("company_name"),
                         "phone": WS.mask_phone(ph),
                         "sector": c.get("sector"),
                         "Meta template": pv.get("template_name") or
                         "no template (%s)" % pv.get("reason"),
                         "approved": pv.get("approved", False),
                         "suppressed": ph in sup,
                         "already started": bool(tracker.get_prospect_state(
                             ph).get("last_sent_day"))})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        names = ["%s · %s" % (c.get("company_name"), WS.mask_phone(
            c.get("phone_e164") or c.get("phone"))) for c in mobiles]
        which = st.selectbox("Preview the exact message for", names,
                             key="wa_preview_who")
        pv = seq_probe.preview(mobiles[names.index(which)], day="day0",
                               language=send_lang)
        if pv["ok"]:
            st.caption("Meta template %s (%s) · parameters: %s" % (
                pv["template_name"], pv["language"],
                ", ".join(v["text"] for v in pv["variables"])))
            C.render(st, text_block(pv["text"] if not pv["fallback"] else
                                    pv["preview"], send_lang == "ar"
                                    and not pv["fallback"]))
        else:
            C.render(st, C.status_pill("No message: %s" % pv["reason"],
                                       "warning"))
limit_bar()
go0 = st.button("Send day 0", type="primary", icon=":material/send:",
                disabled=not mobiles or (real0 and not confirmed0),
                key="wa_btn_day0")
if go0:
    seq = WS.WhatsAppSequence(new_sender(real0), tracker)
    out = []
    bar = st.progress(0.0)
    for i, c in enumerate(mobiles):
        r = seq.start(c, language=send_lang, confirmed=confirmed0)["result"]
        out.append({"company": c.get("company_name"),
                    "phone": WS.mask_phone(r.get("phone")),
                    "template": r.get("template_name"),
                    "status": r["status"], "reason": r["reason"] or ""})
        bar.progress((i + 1) / len(mobiles))
    st.session_state["wa_day0_rows"] = out
    st.rerun()
if st.session_state.get("wa_day0_rows"):
    st.dataframe(pd.DataFrame(st.session_state["wa_day0_rows"]),
                 width="stretch", hide_index=True)

# ── 3. follow-ups ──
C.render(st, C.section_header("3 · Follow-ups (day 2)",
                              "Active prospects whose day 0 went out at "
                              "least 2 days ago."))
due = tracker.get_due_followups()
if due:
    st.dataframe(pd.DataFrame([{
        "company": d.get("company_name"), "phone": WS.mask_phone(d["phone"]),
        "sector": d.get("sector"), "language": d.get("language"),
        "day 0 sent": d.get("last_sent_at")} for d in due]),
        width="stretch", hide_index=True)
else:
    C.render(st, C.empty_state("No follow-ups due",
                               "Day 2 becomes due two days after a real "
                               "day 0 send.", ICONS["clock"]))
real2, confirmed2 = mode_controls("day2")
limit_bar()
if st.button("Process due follow-ups (day 2)",
             icon=":material/schedule_send:", key="wa_btn_day2",
             disabled=not due or (real2 and not confirmed2)):
    st.session_state["wa_day2"] = WS.WhatsAppSequence(
        new_sender(real2), tracker).process_due_followups(
        confirmed=confirmed2)
    st.rerun()
if st.session_state.get("wa_day2"):
    s = st.session_state["wa_day2"]
    C.render(st, C.status_pill(
        "Last run: %(due)d due · %(sent)d sent · %(dry_run)d dry run · "
        "%(blocked)d blocked · %(failed)d failed" % s, "info"))
    if s["items"]:
        st.dataframe(pd.DataFrame(s["items"]), width="stretch",
                     hide_index=True)

# ── 4. status ──
C.render(st, C.section_header("4 · Status", "Today is the Dubai calendar "
                              "day. Delivered / read need Meta webhooks."))
rep = seq_probe.daily_report()
log_rows = WT.read_sent_log()
week_start = ET.dubai_day(ET.utcnow()) - timedelta(days=6)
week = sum(1 for r in log_rows if r.get("status") == "sent"
           and ET.parse_iso(r.get("at"))
           and ET.dubai_day(ET.parse_iso(r["at"])) >= week_start)
states = tracker.all_states()
C.render(st, C.kpi_grid([
    {"label": "Sent today", "value": rep["sent"], "icon_svg": ICONS["send"],
     "delta": "limit %d" % limit},
    {"label": "Remaining today", "value": rep["remaining"],
     "icon_svg": ICONS["clock"]},
    {"label": "Sent this week", "value": week, "icon_svg": ICONS["calendar"]},
    {"label": "Delivered (all time)", "value": sum(s["delivered"]
                                                   for s in states),
     "icon_svg": ICONS["check"]},
    {"label": "Read (all time)", "value": sum(s["read"] for s in states),
     "icon_svg": ICONS["activity"]},
    {"label": "Replies (all time)", "value": sum(s["replies"]
                                                 for s in states),
     "icon_svg": ICONS["inbox"]},
], columns=3))
with st.form("wa_record_event"):
    e1, e2, e3 = st.columns([2, 1, 2])
    ev_phone = e1.text_input("Phone (+971…)")
    ev_kind = e2.selectbox("Event", ["replied", "unsubscribed", "bounced"])
    ev_note = e3.text_input("Reply text / note")
    if st.form_submit_button("Record reply"):
        fn = {"replied": tracker.record_replied,
              "unsubscribed": tracker.record_unsubscribed,
              "bounced": tracker.record_bounced}[ev_kind]
        res = fn(ev_phone, ev_note)
        if res.get("phone"):
            st.success("Recorded %s for %s (status: %s)"
                       % (ev_kind, WS.mask_phone(res["phone"]),
                          res["status"]))
        else:
            st.error("Enter an international phone number (+971…).")
C.render(st, C.section_header("Last 20 sends"))
if log_rows:
    st.dataframe(pd.DataFrame([{
        "at": r.get("at"), "phone": WS.mask_phone(r.get("phone")),
        "company": r.get("company_name"), "template": r.get("template_name")
        or r.get("template_id"), "status": r.get("status"),
        "reason": r.get("reason") or ""} for r in reversed(log_rows[-20:])]),
        width="stretch", hide_index=True)
else:
    C.render(st, C.empty_state("Nothing sent yet", "Dry runs and real sends "
                               "are logged here.", ICONS["inbox"]))

# ── 5. suppression ──
C.render(st, C.section_header("5 · Suppression list",
                              "Never messaged again: replies, STOP, "
                              "undeliverable numbers and manual additions."))
entries = WT.suppression_entries()
if entries:
    st.dataframe(pd.DataFrame([{"phone": p, "reason": v.get("reason"),
                                "added": v.get("at")}
                               for p, v in sorted(entries.items())]),
                 width="stretch", hide_index=True)
else:
    C.render(st, C.status_pill("The suppression list is empty.", "neutral"))
with st.form("wa_add_suppression"):
    a1, a2 = st.columns(2)
    sup_phone = a1.text_input("Phone to suppress (+971…)")
    sup_reason = a2.text_input("Reason", "manual")
    if st.form_submit_button("Add to suppression list"):
        res = WS.add_to_suppression(sup_phone, sup_reason or "manual")
        if res["ok"]:
            st.success("%s %s" % (WS.mask_phone(res["phone"]), "added"
                                  if res["added"] else "was already listed"))
        else:
            st.error("Enter an international phone number (+971…).")
buf = io.StringIO()
w = csv.writer(buf)
w.writerow(["phone", "reason", "added"])
for p, v in sorted(entries.items()):
    w.writerow([p, v.get("reason", ""), v.get("at", "")])
st.download_button("Export CSV", buf.getvalue().encode("utf-8-sig"),
                   file_name="whatsapp_suppression.csv", mime="text/csv",
                   icon=":material/download:", key="wa_dl_suppression")
