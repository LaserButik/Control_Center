# -*- coding: utf-8 -*-
"""Funnel Analytics — Visualize the customer journey and drop-offs."""

import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.graph_objects as go

from ui_common import page_config, render_sidebar, page_header, ROOT
from ui.i18n import t, get_lang

page_config(st, "Funnel Analytics")
render_sidebar(st)
lang = get_lang()
page_header(st, "Funnel Analytics", 
"Track exactly where prospects drop off in the customer journey.", 
"analytics")

def _get_env(key):
    val = os.getenv(key, "").strip()
    if not val:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    return val

@st.cache_data(ttl=60) # تحديث الكاش كل دقيقة بدلاً من 5 دقائق
def fetch_brevo_stats():
    api_key = _get_env("BREVO_API_KEY")
    if not api_key:
        return {"sent": 0, "delivered": 0, "opened": 0, "clicks": 0}

    headers = {"api-key": api_key, "accept": "application/json"}
    try:
        # جلب تاريخ الأمس لتجنب خطأ Brevo
        safe_end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        url = "https://api.brevo.com/v3/smtp/statistics/aggregatedReport"
        params = {"startDate": "2026-09-01", "endDate": safe_end_date}
        
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # معالجة مشكلة None التي تظهر في Brevo
            sent = data.get("sent") or data.get("delivered") or 0
            return {
                "sent": sent,
                "delivered": data.get("delivered") or 0,
                "opened": data.get("uniqueOpens") or 0,
                "clicks": data.get("uniqueClicks") or 0
            }
    except Exception:
        pass
    return {"sent": 0, "delivered": 0, "opened": 0, "clicks": 0}

def get_local_stats():
    indo_file = ROOT / "data" / "email" / "indoctrination_state.json"
    replies = 0
    if indo_file.exists():
        try:
            state = json.loads(indo_file.read_text(encoding="utf-8"))
            replies = len([k for k, v in state.items() if v.get("status") == "replied"])
        except: pass

    sales_file = ROOT / "data" / "email" / "sales_log.jsonl"
    meetings = 0
    payments = 0
    if sales_file.exists():
        for line in sales_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    e = json.loads(line)
                    if e.get("action") == "meeting_link": meetings += 1
                    if e.get("action") == "payment_link": payments += 1
                except: pass
    return replies, meetings, payments

# جمع البيانات
brevo = fetch_brevo_stats()
replies, meetings, payments = get_local_stats()

sent = brevo["sent"]
delivered = brevo["delivered"]
opened = brevo["opened"]
clicked = brevo["clicks"]

st.write("")
st.subheader("Customer Journey Funnel")

# رسم القمع
fig = go.Figure(go.Funnel(
    y = ["Sent", "Delivered", "Opened", "Clicked Link", "Replied", "Meeting Booked", "Paid"],
    x = [sent, delivered, opened, clicked, replies, meetings, payments],
    textinfo = "value+percent initial",
    marker = {"color": ["#667eea", "#764ba2", "#10b981", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899"]}
))

fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#a0aec0', size=14),
    margin=dict(l=20, r=20, t=20, b=20),
    height=450
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# تحليل أين يتوقف العميل
st.subheader("Drop-off Analysis (Where to focus)")

col1, col2, col3 = st.columns(3)

with col1:
    if opened > 0:
        click_rate = (clicked / opened) * 100
        st.metric("Open to Click Rate", f"{click_rate:.1f}%")
        if click_rate < 5:
            st.warning("⚠️ People open but don't click. Your link is not compelling.")
        else:
            st.success("✅ Good click rate.")

with col2:
    if clicked > 0:
        reply_rate = (replies / clicked) * 100
        st.metric("Click to Reply Rate", f"{reply_rate:.1f}%")
        if reply_rate < 5:
            st.warning("⚠️ They visit but don't reply. Your page doesn't convince them.")
        else:
            st.success("✅ Good reply rate.")

with col3:
    if replies > 0:
        meeting_rate = (meetings / replies) * 100
        st.metric("Reply to Meeting Rate", f"{meeting_rate:.1f}%")
        if meeting_rate < 30:
            st.warning("⚠️ People reply but don't book. Your reply handling is slow.")
        else:
            st.success("✅ Good conversion to meetings.")

st.divider()
st.info("""
**ملاحظة هامة:** 
لظهور مرحلة "Clicked Link" (الضغط على الرابط) في الرسم البياني، يجب أن يكون العميل قد ضغط على زر "Try ALPHA" في الإيميل الجديد. 
إذا كان الرقم لا يزال 0، انتظر بضع دقائق (لأن Brevo يتأخر في تحديث البيانات)، أو تأكد من أنك قمت بالضغط على الزر في آخر إيميل تجريبي.
""")