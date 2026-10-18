# -*- coding: utf-8 -*-
"""Social Media Center — Control your LinkedIn and Facebook posts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from ui_common import page_config, render_sidebar, page_header
from atlas_services import social_engine

page_config(st, "Social Media")
render_sidebar(st)
page_header(st, "Social Media Center", 
            "Generate and publish viral content automatically.", 
            "share")

st.info("🤖 نظام النشر التلقائي يعمل كل صباح في الساعة 9:00. استخدم هذا الزر للنشر الفوري فقط.")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Settings & Publishing")
    
    image_mode = st.radio(
        "اختر نوع الصور المرفقة:",
        options=["ai", "none", "personal"],
        format_func=lambda x: {
            "ai": "🤖 صور مولدة بالذكاء الاصطناعي (DALL-E)",
            "none": "📝 نص فقط (بدون صور - احترافي جداً)",
            "personal": "📸 صوري الشخصية (من مجلد images)"
        }[x],
        horizontal=False
    )
    
    st.write("")
    if st.button("🚀 توليد ونشر الآن (يدوياً)", type="primary", use_container_width=True):
        with st.spinner("جاري التوليد والنشر..."):
            res = social_engine.run_daily_social(dry_run=False, image_mode=image_mode)
            if res.get("ok"):
                st.success("✅ تمت العملية بنجاح!")
                st.write(f"**LinkedIn:** {'✅ نجح' if res.get('linkedin', {}).get('ok') else '❌ فشل'}")
                st.write(f"**Facebook:** {'✅ نجح' if res.get('facebook', {}).get('ok') else '❌ فشل'}")
            else:
                st.error(f"فشل: {res.get('reason')}")

with col2:
    st.subheader("إحصائيات")
    if social_engine.POSTED_FILE.exists():
        history = json.loads(social_engine.POSTED_FILE.read_text(encoding="utf-8"))
        st.metric("إجمالي المنشورات", len(history))
    else:
        st.metric("إجمالي المنشورات", 0)

st.divider()
st.subheader("📜 سجل المنشورات السابقة")

if social_engine.POSTED_FILE.exists():
    history = json.loads(social_engine.POSTED_FILE.read_text(encoding="utf-8"))
    for idx, item in enumerate(reversed(history[-5:])):
        date_str = item.get('date', '')[:16]
        mode_str = item.get('image_mode', 'N/A')
        with st.expander(f"📅 {date_str} | Mode: {mode_str}"):
            # استخدام idx لضمان عدم تكرار الـ ID
            st.markdown(f"**LinkedIn:** {'✅ نجح' if item.get('linkedin_result', {}).get('ok') else '❌ فشل'}")
            st.text_area("English Content", item.get('linkedin_content', ''), height=100, disabled=True, key=f"li_{idx}_{date_str}")
            
            st.markdown(f"**Facebook:** {'✅ نجح' if item.get('facebook_result', {}).get('ok') else '❌ فشل'}")
            st.text_area("Arabic Content", item.get('facebook_content', ''), height=100, disabled=True, key=f"fb_{idx}_{date_str}")
else:
    st.info("لا توجد منشورات سابقة بعد.")