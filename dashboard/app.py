import streamlit as st
import requests
import time
import os
from components import render_kpis, render_chapter_performance, render_live_monitor

# Page Configuration
st.set_page_config(
    page_title="CallSakhi Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load CSS
css_path = os.path.join(os.path.dirname(__file__), "style.css")
with open(css_path) as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# API Base URL (Assuming FastAPI runs on 8000 locally)
API_BASE = "http://127.0.0.1:8000/api/analytics"

st.markdown('<h1 style="color: #F9FAFB;">Analytics Dashboard — Impact Measurement</h1>', unsafe_allow_html=True)
st.markdown('<h3 style="color: #F9FAFB; margin-top: 1rem;">📊 Analytics Dashboard — The Proof-Maker</h3>', unsafe_allow_html=True)
st.markdown('<p style="color: #CBD5E1; font-style: italic;">Built for NGOs & Government — turn code into a verified Social Impact Project</p>', unsafe_allow_html=True)

# Fetch Data
@st.cache_data(ttl=5) # Cache data for 5 seconds to simulate real-time without overwhelming the server
def fetch_kpis():
    try:
        return requests.get(f"{API_BASE}/kpis").json()
    except:
        return {"error": "connection failed"}

@st.cache_data(ttl=5)
def fetch_chapters():
    try:
        return requests.get(f"{API_BASE}/chapter-performance").json()
    except:
        return {"error": "connection failed"}

@st.cache_data(ttl=5)
def fetch_live():
    try:
        return requests.get(f"{API_BASE}/live-monitor").json()
    except:
        return {"error": "connection failed"}

kpis = fetch_kpis()
chapters = fetch_chapters()
live_data = fetch_live()

# Render Dashboard
render_kpis(kpis)

st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    render_live_monitor(live_data)

with col2:
    render_chapter_performance(chapters)

# Auto-refresh button (Streamlit trick)
if st.button("Refresh Telemetry"):
    st.rerun()
