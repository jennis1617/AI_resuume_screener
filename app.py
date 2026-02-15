"""
AI-Powered Resume Screening System - Main Application
Built with Groq for Ultra-Fast LLM Processing
"""

import os
import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from PIL import Image

# Load .env if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from config.settings import PAGE_CONFIG, CUSTOM_CSS
from utils.groq_client import init_groq_client
from utils.sharepoint import SHAREPOINT_AVAILABLE, SHAREPOINT_ERROR
from ui.tabs import render_upload_tab, render_database_tab, render_matching_tab, render_analytics_tab

# ── Page Configuration ─────────────────────────────────────────────────────────
st.set_page_config(**PAGE_CONFIG)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Session State Initialisation ───────────────────────────────────────────────
defaults = {
    'parsed_resumes': [],
    'candidates_df': None,
    'matched_results': None,
    'resume_texts': {},
    'resume_metadata': {},

    # ADD THIS
    'downloaded_resumes': [],

    'sharepoint_config': {
        'tenant_id': os.getenv('TENANT_ID', ''),
        'client_id': os.getenv('CLIENT_ID', ''),
        'client_secret': os.getenv('CLIENT_SECRET', ''),
        'site_id': os.getenv('SITE_ID', ''),
        'drive_id': os.getenv('DRIVE_ID', ''),
        'input_folder_path': os.getenv('INPUT_FOLDER_PATH', ''),
        'output_folder_path': os.getenv('OUTPUT_FOLDER_PATH', ''),
        'connected': False,
    },
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Main ───────────────────────────────────────────────────────────────────────
def main():

    # Header
    st.markdown('<div class="nexturn-header">', unsafe_allow_html=True)
    try:
        logo = Image.open("logo.png")
        col1, col2, col3 = st.columns([1, 1.3, 1])
        with col2:
            st.image(logo, width=400)
    except FileNotFoundError:
        st.error("⚠️ Logo file 'logo.png' not found")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:

        st.title("⚙️ Configuration")

        # ── Groq API Keys ──────────────────────────────────────────────────────
        st.subheader("🔑 Groq API Keys")

        groq_api_key = st.text_input(
            "Primary Groq API Key",
            type="password",
            value=st.session_state.get('groq_api_key', os.getenv('GROQ_API_KEY', '')),
        )

        groq_fallback_key = st.text_input(
            "Fallback Groq API Key (optional)",
            type="password",
            value=st.session_state.get('groq_fallback_key', os.getenv('GROQ_FALLBACK_API_KEY', '')),
        )

        client = None
        fallback_client = None

        if groq_api_key:
            st.session_state['groq_api_key'] = groq_api_key
            try:
                client = init_groq_client(groq_api_key)
                st.success("✅ Primary key connected")
            except Exception:
                st.error("❌ Primary key invalid")

        if groq_fallback_key:
            st.session_state['groq_fallback_key'] = groq_fallback_key
            try:
                fallback_client = init_groq_client(groq_fallback_key)
                st.info("🔄 Fallback key ready")
            except Exception:
                st.warning("⚠️ Fallback key invalid")

        st.divider()

        # ── Privacy ────────────────────────────────────────────────────────────
        st.subheader("🛡️ Privacy Settings")
        mask_pii_enabled = st.checkbox("Enable PII Masking", value=True)

        st.divider()

        # ── SharePoint Configuration ───────────────────────────────────────────
        sp = st.session_state.sharepoint_config

        st.subheader("☁️ SharePoint")

        with st.expander("☁️ SharePoint Configuration", expanded=False):
            st.info("Loaded from .env file")
            st.text(f"Site ID: {sp.get('site_id')}")
            st.text(f"Drive ID: {sp.get('drive_id')}")
            st.text(f"Input Folder: {sp.get('input_folder_path')}")
            st.text(f"Output Folder: {sp.get('output_folder_path')}")

        if st.button("🔗 Connect to SharePoint", use_container_width=True):

            required = [
                sp.get('tenant_id'),
                sp.get('client_id'),
                sp.get('client_secret'),
                sp.get('site_id'),
                sp.get('drive_id')
            ]

            if all(required):
                try:
                    import msal

                    authority = f"https://login.microsoftonline.com/{sp['tenant_id']}"

                    msal_app = msal.ConfidentialClientApplication(
                        sp['client_id'],
                        authority=authority,
                        client_credential=sp['client_secret'],
                    )

                    token_res = msal_app.acquire_token_for_client(
                        scopes=["https://graph.microsoft.com/.default"]
                    )

                    if "access_token" in token_res:
                        sp['connected'] = True
                        st.session_state.sharepoint_config = sp
                        st.success("✅ SharePoint Connected")
                        st.rerun()
                    else:
                        st.error("Auth failed")

                except Exception as e:
                    st.error(f"Connection error: {e}")

            else:
                st.error("Missing values in .env")

        # ── Date Filter ────────────────────────────────────────────────────────
        st.subheader("📅 Resume Submission Date Range")
        use_date_filter = st.checkbox("Enable date range filter", value=False)

        start_date = end_date = None

        if use_date_filter:
            if st.session_state.candidates_df is not None and 'submission_date' in st.session_state.candidates_df.columns:
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

        st.divider()

        # ── Top N ──────────────────────────────────────────────────────────────
        st.subheader("🎚️ Top Candidates")
        top_n = st.select_slider(
            "Select number",
            options=[1, 2, 3, 5, 10, 15, 20],
            value=5,
        )

    # ── Store config ───────────────────────────────────────────────────────────
    st.session_state['mask_pii_enabled'] = mask_pii_enabled
    st.session_state['use_date_filter'] = use_date_filter
    st.session_state['start_date'] = start_date
    st.session_state['end_date'] = end_date
    st.session_state['top_n'] = top_n
    st.session_state['client'] = client
    st.session_state['fallback_client'] = fallback_client

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload Resumes",
        "📊 Candidate Pool",
        "🎯 AI Matching",
        "📈 Analytics Dashboard",
    ])

    with tab1:
        render_upload_tab()
    with tab2:
        render_database_tab()
    with tab3:
        render_matching_tab()
    with tab4:
        render_analytics_tab()

    st.divider()


if __name__ == "__main__":
    main()
