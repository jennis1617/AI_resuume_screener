"""
AI-Powered Resume Screening System - Main Application
Built with Groq for Ultra-Fast LLM Processing
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from PIL import Image

from config.settings import PAGE_CONFIG, CUSTOM_CSS
from utils.groq_client import init_groq_client
from utils.sharepoint import SHAREPOINT_AVAILABLE, SHAREPOINT_ERROR
from ui.tabs import render_upload_tab, render_database_tab, render_matching_tab, render_analytics_tab

# Page Configuration
st.set_page_config(**PAGE_CONFIG)

# Custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Initialize session state
if 'parsed_resumes' not in st.session_state:
    st.session_state.parsed_resumes = []
if 'candidates_df' not in st.session_state:
    st.session_state.candidates_df = None
if 'matched_results' not in st.session_state:
    st.session_state.matched_results = None
if 'resume_texts' not in st.session_state:
    st.session_state.resume_texts = {}
if 'resume_metadata' not in st.session_state:
    st.session_state.resume_metadata = {}
if 'sharepoint_config' not in st.session_state:
    st.session_state.sharepoint_config = {
        'site_url': '',
        'username': '',
        'password': '',
        'folder_path': '',
        'connected': False
    }

def main():
    # Header with Logo
    st.markdown('<div class="nexturn-header">', unsafe_allow_html=True)
    
    # NEXTURN Logo - Centered and Properly Sized
    try:
        logo = Image.open("logo.png")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(logo, width=400)
    except FileNotFoundError:
        st.error("⚠️ Logo file 'logo.png' not found in the app folder")
    
    # Elegant Divider
    st.markdown('<hr style="margin: 20px 0; border: none; border-top: 2px solid #e0e0e0;">', unsafe_allow_html=True)
    
    # Title Section
    st.markdown("""
    <h1 style="font-size: 3rem; font-weight: 700; color: #1a1a1a; text-align: center; margin: 15px 0 10px 0; letter-spacing: -0.5px;">
        AI Resume Screening System
    </h1>
    <p style="font-size: 1.15rem; color: #666; text-align: center; margin-bottom: 10px;">
        ⚡ Powered by Groq | Automated Intelligent Recruitment
    </p>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sidebar Configuration
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        groq_api_key = st.text_input(
            "🔑 Groq API Key",
            type="password",
            value=st.session_state.get('groq_api_key', ''),
            help="Get free key: https://console.groq.com"
        )
        
        if groq_api_key:
            st.session_state['groq_api_key'] = groq_api_key
            try:
                client = init_groq_client(groq_api_key)
                st.success("✅ Connected")
            except:
                st.error("❌ Invalid Key")
                client = None
        else:
            st.warning("⚠️ Enter API Key")
            client = None
        
        st.divider()
        
        # PII Masking Toggle
        st.subheader("🛡️ Privacy Settings")
        mask_pii_enabled = st.checkbox("Enable PII Masking", value=True, help="Redact emails and phone numbers before sending to LLM")
        
        st.divider()
        
        # Date Range Filter with Slider
        st.subheader("📅 Resume Submission Date Range")
        use_date_filter = st.checkbox("Enable date range filter", value=False)
        
        if use_date_filter:
            # Get min and max dates from existing data
            if st.session_state.candidates_df is not None and 'submission_date' in st.session_state.candidates_df.columns:
                try:
                    df_dates = pd.to_datetime(st.session_state.candidates_df['submission_date'])
                    min_date = df_dates.min().date()
                    max_date = df_dates.max().date()
                except:
                    min_date = datetime.now().date() - timedelta(days=90)
                    max_date = datetime.now().date()
            else:
                min_date = datetime.now().date() - timedelta(days=90)
                max_date = datetime.now().date()
            
            # Date range slider
            date_range = st.slider(
                "Select date range",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date),
                format="YYYY-MM-DD"
            )
            start_date, end_date = date_range
            
            st.info(f"📅 Filtering: {start_date} to {end_date}")
        else:
            start_date = None
            end_date = None
        
        st.divider()
        
        st.subheader("🎚️ Top Candidates to Review")
        top_n = st.select_slider(
            "Select number",
            options=[1, 2, 3, 5, 10, 15, 20],
            value=5
        )
        
        if top_n <= 3:
            st.warning("⚡ Urgent hiring mode")
        elif top_n <= 5:
            st.info("📅 Standard recruitment")
        else:
            st.success("🕐 Comprehensive review")
    
    # Store configuration in session state
    st.session_state['mask_pii_enabled'] = mask_pii_enabled
    st.session_state['use_date_filter'] = use_date_filter
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date
    st.session_state['top_n'] = top_n
    st.session_state['client'] = client
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload Resumes", "📊 Candidate Pool", "🎯 AI Matching", "📈 Analytics Dashboard"])
    
    with tab1:
        render_upload_tab()
    
    with tab2:
        render_database_tab()
    
    with tab3:
        render_matching_tab()
    
    with tab4:
        render_analytics_tab()
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🚀 AI Resume Screening System v2.1 | Automated Intelligent Recruitment | Built with Streamlit & Groq</p>
        <p style="font-size: 0.85em;">© 2024 NEXTURN. All rights reserved.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()