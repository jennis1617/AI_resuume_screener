"""
AI-Powered Resume Screening System - Main Application
Built with Groq for Ultra-Fast LLM Processing
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from config.settings import PAGE_CONFIG, CUSTOM_CSS
from utils.groq_client import init_groq_client
from ui.tabs import render_upload_tab, render_analytics_tab
from ui.analysis_tab import render_analysis_tab
from ui.candidate_pool_tab import render_candidate_pool_tab

st.set_page_config(**PAGE_CONFIG)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
_defaults = {
    'parsed_resumes': [],
    'candidates_df': None,
    'matched_results': None,
    'review_results': None,
    'selected_for_pool': set(),
    'resume_texts': {},
    'resume_metadata': {},
    'sharepoint_config': {
        'tenant_id': os.getenv('TENANT_ID', ''),
        'client_id': os.getenv('CLIENT_ID', ''),
        'client_secret': os.getenv('CLIENT_SECRET', ''),
        'site_id': os.getenv('SHAREPOINT_SITE_ID', ''),
        'drive_id': os.getenv('SHAREPOINT_DRIVE_ID', ''),
        'input_folder_path': os.getenv('INPUT_FOLDER_PATH', 'Demair/Sample resumes'),
        'output_folder_path': os.getenv('OUTPUT_FOLDER_PATH', 'Demair/Resumes_database'),
        'connected': False,
    },
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def _init_clients():
    client = None
    fallback_client = None
    primary_key = os.getenv('GROQ_API_KEY', '')
    fallback_key = os.getenv('GROQ_FALLBACK_API_KEY', '')
    if primary_key:
        try:
            client = init_groq_client(primary_key)
        except Exception:
            pass
    if fallback_key:
        try:
            fallback_client = init_groq_client(fallback_key)
        except Exception:
            pass
    return client, fallback_client


def _init_sharepoint():
    sp = st.session_state.sharepoint_config
    if sp.get('connected'):
        return
    required = [sp.get('tenant_id'), sp.get('client_id'),
                sp.get('client_secret'), sp.get('site_id'), sp.get('drive_id')]
    if not all(required):
        return
    try:
        import msal
        authority = f"https://login.microsoftonline.com/{sp['tenant_id']}"
        msal_app = msal.ConfidentialClientApplication(
            sp['client_id'], authority=authority, client_credential=sp['client_secret'],
        )
        token_res = msal_app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" in token_res:
            sp['connected'] = True
            st.session_state.sharepoint_config = sp
    except Exception:
        pass


def main():
    client, fallback_client = _init_clients()
    _init_sharepoint()

    st.session_state['client'] = client
    st.session_state['fallback_client'] = fallback_client

    # ── Header ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="nexturn-header">', unsafe_allow_html=True)
    try:
        logo = Image.open("logo.png")
        col1, col2, col3 = st.columns([1, 1.3, 1])
        with col2:
            st.image(logo, width=400)
    except FileNotFoundError:
        st.error("⚠️ Logo file 'logo.png' not found in the app folder")

    st.markdown('<hr style="margin: 20px 0; border: none; border-top: 2px solid #e0e0e0;">', unsafe_allow_html=True)
    st.markdown("""
    <h1 style="font-size: 3rem; font-weight: 700; color: #1a1a1a; text-align: center;
               margin: 15px 0 10px 0; letter-spacing: -0.5px;">
          Resume Screening System
    </h1>
    <p style="font-size: 1.15rem; color: #666; text-align: center; margin-bottom: 10px;">
         Powered by Groq | Automated Intelligent Recruitment
    </p>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Sidebar ─────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("⚙️ Settings")

        st.subheader("🛡️ Privacy")
        mask_pii_enabled = st.checkbox(
            "Hide personal details when sending to AI(**PII Masking**)",
            value=True,
            help="Redacts email addresses and phone numbers before any AI processing"
        )

        st.divider()

        st.subheader("📅 Filter by Date Received")
        use_date_filter = st.checkbox("Turn on date filter", value=False)

        start_date = end_date = None
        if use_date_filter:
            if (st.session_state.candidates_df is not None and
                    'submission_date' in st.session_state.candidates_df.columns):
                try:
                    df_dates = pd.to_datetime(st.session_state.candidates_df['submission_date'])
                    min_date = df_dates.min().date()
                    max_date = df_dates.max().date()
                except Exception:
                    min_date = datetime.now().date() - timedelta(days=90)
                    max_date = datetime.now().date()
            else:
                min_date = datetime.now().date() - timedelta(days=90)
                max_date = datetime.now().date()

            date_range = st.slider(
                "Select date range",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date),
                format="YYYY-MM-DD",
            )
            start_date, end_date = date_range
            st.info(f"📅 Showing: {start_date} to {end_date}")

    st.session_state['mask_pii_enabled'] = mask_pii_enabled
    st.session_state['use_date_filter'] = use_date_filter
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date

    # ── 4 Tabs (pre-screening removed) ────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload/Retrieve Resumes",
        "🎯 Candidate Review & Scoring",
        "👥 Candidate Pool",
        "📈 Analytics",
    ])

    with tab1:
        render_upload_tab()

    with tab2:
        parsed_resumes = st.session_state.get('parsed_resumes', [])
        client_obj = st.session_state.get('client')
        if parsed_resumes and client_obj:
            render_analysis_tab(parsed_resumes, client_obj)
        else:
            st.info("📤 Please upload and process resumes in the **Upload Resumes** tab first.")

    with tab3:
        render_candidate_pool_tab()

    with tab4:
        render_analytics_tab()

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>AI Resume Screening System | Automated Intelligent Recruitment | Built with Streamlit & Groq</p>
        <p style="font-size: 0.85em;">© 2026 NEXTURN. All rights reserved.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()