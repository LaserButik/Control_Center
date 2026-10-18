# -*- coding: utf-8 -*-
"""Sales & Replies — Manage interested prospects and send payment/meeting links."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from ui_common import page_config, render_sidebar, page_header, ROOT
from ui.i18n import t, get_lang
from atlas_services import sales_sequence

page_config(st, "Sales & Replies")
render_sidebar(st)
lang = get_lang()
page_header(st, "Sales & Replies", 
            "Send payment or meeting links to interested prospects.", 
            "sales")

DATA_DIR = ROOT / "data" / "email"
SENT_LOG = DATA_DIR / "sent_log.jsonl"
INDO_STATE = DATA_DIR / "indoctrination_state.json"

# جلب الإيميلات التي ردت (أو التي تم وضع علامة عليها كـ replied)
replied_prospects = []
state = {}
if INDO_STATE.exists():
    try:
        state = json.loads(INDO_STATE.read_text(encoding="utf-8"))
        for email, data in state.items():
            if data.get("status") == "replied":
                replied_prospects.append({"email": email, "company": data.get("company_name", "Unknown")})
    except: pass

# إذا لم توجد ردود حقيقية (لأن IMAP غير مفعل)، نضيف زر لمحاكاة الردود للتجربة
st.subheader("1. Interested Prospects")
if not replied_prospects:
    st.info("لا توجد ردود مسجلة حالياً. (بما أن IMAP غير مفعل، يمكنك إضافة عميل يدوياً هنا للتجربة).")
    
    with st.form("manual_add"):
        col1, col2 = st.columns(2)
        with col1:
            manual_email = st.text_input("Email Address")
        with col2:
            manual_company = st.text_input("Company Name")
        submitted = st.form_submit_button("Mark as Interested")
        if submitted and manual_email:
            state[manual_email] = {"company_name": manual_company, "status": "replied", "language": "en"}
            INDO_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success("Added successfully! Refresh to see.")
            st.rerun()
else:
    st.write(f"لديك **{len(replied_prospects)}** عميل مهتم جاهز للإغلاق.")

st.divider()

# ══════════════════════════════════════════════════════════════════
# إرسال الروابط
# ══════════════════════════════════════════════════════════════════
st.subheader("2. Send Link")
st.caption("اختر عميلاً من القائمة، ثم اختر نوع الرابط الذي تريد إرساله له.")

if replied_prospects:
    selected_email = st.selectbox(
        "Select Prospect", 
        options=[p["email"] for p in replied_prospects],
        format_func=lambda x: f"{x} ({next((p['company'] for p in replied_prospects if p['email'] == x), '')})"
    )
    
    prospect = {"email": selected_email, "company_name": next((p['company'] for p in replied_prospects if p['email'] == selected_email), "")}
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📅 Send Meeting Link (Calendly)", use_container_width=True, type="primary"):
            with st.spinner("Sending Meeting Link..."):
                res = sales_sequence.send_meeting_link(prospect, dry_run=False)
                if res.get("status") == "sent":
                    st.success(f"✅ Meeting link sent to {selected_email}!")
                else:
                    st.error(f"❌ Failed: {res.get('reason')}")
                    
    with col2:
        if st.button("💳 Send Payment Link (Stripe)", use_container_width=True):
            with st.spinner("Sending Payment Link..."):
                res = sales_sequence.send_payment_link(prospect, dry_run=False)
                if res.get("status") == "sent":
                    st.success(f"✅ Payment link sent to {selected_email}!")
                else:
                    st.error(f"❌ Failed: {res.get('reason')}")

st.divider()
st.subheader("3. Sales Log (Last 10)")
SALES_LOG = DATA_DIR / "sales_log.jsonl"
if SALES_LOG.exists():
    logs = []
    for line in SALES_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try: logs.append(json.loads(line))
            except: pass
    
    if logs:
        for log in reversed(logs[-10:]):
            date = log.get("at", "")[:16]
            email = log.get("email", "")
            action = "Meeting" if log.get("action") == "meeting_link" else "Payment"
            status = log.get("status", "")
            st.markdown(f"- **{date}** | {email} | {action} | Status: `{status}`")
    else:
        st.info("No sales links sent yet.")
else:
    st.info("No sales log found.")