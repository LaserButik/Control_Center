# -*- coding: utf-8 -*-
"""Redirect: this was the old Dashboard page. Now redirects to Home."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: F401,E402

import streamlit as st

st.set_page_config(page_title="Redirecting...", page_icon=":material/hub:")
st.switch_page("app.py")
