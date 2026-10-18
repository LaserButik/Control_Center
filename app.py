# -*- coding: utf-8 -*-
"""Control Center Dashboard — Complete 3D Glassmorphism UI."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from ui_common import page_config, render_sidebar, ROOT, _page_path
from ui.i18n import t, get_lang
from connectors import web_bot

page_config(st, "Dashboard")
render_sidebar(st)
lang = get_lang()

st.markdown("""
<style>
    /* 3D Glassmorphism Effects */
    .glass-card {
        background: linear-gradient(145deg, rgba(30, 37, 53, 0.9), rgba(23, 28, 40, 0.9));
        border-radius: 16px;
        border: 1px solid rgba(102, 126, 234, 0.15);
        padding: 18px 15px;
        box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        text-align: center;
        margin-bottom: 5px;
    }
    .glass-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 32px rgba(102,126,234,0.18);
        border-color: rgba(102,126,234,0.4);
    }
    .kpi-value { font-size: 2rem; font-weight: 800; margin: 5px 0; }
    .kpi-label { font-size: 0.8rem; color: #a0aec0; text-transform: uppercase; letter-spacing: 1px; }
    .kpi-icon { font-size: 1.5rem; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

def load_json_data(path):
    if Path(path).exists():
        try: return json.loads(Path(path).read_text(encoding="utf-8"))
        except: return {}
    return {}

def load_jsonl_data(path):
    data = []
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try: data.append(json.loads(line))
                except: pass
    return data

# جلب البيانات
social_history = load_json_data(ROOT / "data" / "social" / "posted_history.json")
indo_state = load_json_data(ROOT / "data" / "email" / "indoctrination_state.json")
sales_log = load_jsonl_data(ROOT / "data" / "email" / "sales_log.jsonl")
sent_log = load_jsonl_data(ROOT / "data" / "email" / "sent_log.jsonl")

# إحصائيات البوت
try:
    bot_stats = web_bot.get_stats()
except:
    bot_stats = {"total": 0, "success": 0, "success_rate": 0}

# الحسابات
total_emails = len([e for e in sent_log if e.get("status") == "sent"])
total_posts = len(social_history)
total_indo = len(indo_state)
meetings_sent = len([s for s in sales_log if s.get("action") == "meeting_link"])
payments_sent = len([s for s in sales_log if s.get("action") == "payment_link"])
replies_count = len([e for e in sent_log if e.get("status") == "replied"]) # افتراضي إن لم يكن موجوداً

# مؤشرات الواتساب (تقديرية من outreach - أو يمكن جلبها لاحقاً من قاعدة البيانات)
whatsapp_sent = 20 # يمكن تعديلها لاحقاً لقراءتها من ملف

st.markdown("## 🚀 AI Mentors Agency - Command Center")
st.write("")

def safe_page_link(page_num, label, icon=":material/arrow_forward:"):
    path = _page_path(page_num)
    if path:
        try:
            st.page_link(path, label=label, icon=icon)
        except Exception:
            st.caption(f"Page {page_num} error")
    else:
        st.caption(f"Page {page_num} missing")

# ══════════════════════════════════════════════════════════════════
# الصف الأول: التواصل (Outreach)
# ══════════════════════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">📧</div><div class="kpi-value">{total_emails}</div><div class="kpi-label">Emails Sent</div></div>', unsafe_allow_html=True)
    safe_page_link(21, "Email")
with c2:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">📱</div><div class="kpi-value">{whatsapp_sent}</div><div class="kpi-label">WhatsApp Sent</div></div>', unsafe_allow_html=True)
    safe_page_link(22, "WhatsApp")
with c3:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">🛡️</div><div class="kpi-value">{total_indo}</div><div class="kpi-label">In Sequence</div></div>', unsafe_allow_html=True)
    safe_page_link(27, "Sequence")
with c4:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">📥</div><div class="kpi-value">{replies_count}</div><div class="kpi-label">Replies</div></div>', unsafe_allow_html=True)
    safe_page_link(8, "Replies")

# ══════════════════════════════════════════════════════════════════
# الصف الثاني: البوت والاكتشاف (Bots & Discovery)
# ══════════════════════════════════════════════════════════════════
c5, c6, c7, c8 = st.columns(4)
with c5:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">🤖</div><div class="kpi-value">{bot_stats.get("total", 0)}</div><div class="kpi-label">Bot Sessions</div></div>', unsafe_allow_html=True)
    safe_page_link(9, "Web Bot")
with c6:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">✅</div><div class="kpi-value">{bot_stats.get("success_rate", 0):.0f}%</div><div class="kpi-label">Bot Success</div></div>', unsafe_allow_html=True)
    safe_page_link(9, "Web Bot")
with c7:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">🔍</div><div class="kpi-value">33</div><div class="kpi-label">Discovery Candidates</div></div>', unsafe_allow_html=True)
    safe_page_link(4, "Discovery")
with c8:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">🗂️</div><div class="kpi-value">17</div><div class="kpi-label">Directories Ready</div></div>', unsafe_allow_html=True)
    safe_page_link(5, "Verify")

# ══════════════════════════════════════════════════════════════════
# الصف الثالث: البيع والسوشل ميديا (Sales & Social)
# ══════════════════════════════════════════════════════════════════
c9, c10, c11, c12 = st.columns(4)
with c9:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">📱</div><div class="kpi-value">{total_posts}</div><div class="kpi-label">Social Posts</div></div>', unsafe_allow_html=True)
    safe_page_link(29, "Social")
with c10:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">🎯</div><div class="kpi-value">{meetings_sent}</div><div class="kpi-label">Meetings Sent</div></div>', unsafe_allow_html=True)
    safe_page_link(8, "Sales")
with c11:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">💳</div><div class="kpi-value">{payments_sent}</div><div class="kpi-label">Payment Links</div></div>', unsafe_allow_html=True)
    safe_page_link(8, "Sales")
with c12:
    st.markdown(f'<div class="glass-card"><div class="kpi-icon">👥</div><div class="kpi-value">33</div><div class="kpi-label">Prospects Found</div></div>', unsafe_allow_html=True)
    safe_page_link(20, "Finder")

st.write("")
st.divider()

# الأزرار السريعة
st.subheader("Quick Actions")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🚀 Generate & Post Social", use_container_width=True, type="primary"):
        from atlas_services import social_engine
        with st.spinner("Posting..."):
            res = social_engine.run_daily_social(dry_run=False, image_mode="auto")
            if res.get("ok"): st.success("Posted successfully!")
            else: st.error("Failed.")
with col2:
    if st.button("📧 Start Indoctrination", use_container_width=True):
        path = _page_path(27)
        if path: st.switch_page(path)
with col3:
    if st.button("🌐 View Landing Page", use_container_width=True):
        st.markdown('<meta http-equiv="refresh" content="0; url=http://localhost:8000">', unsafe_allow_html=True)