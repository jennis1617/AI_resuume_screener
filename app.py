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
from login import render_login_page, render_user_badge

st.set_page_config(**PAGE_CONFIG)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown("""
<style>
div[data-testid="stExpander"] summary p,
div[data-testid="stExpander"] summary span {
    font-size: 1.18rem !important;
    font-weight: 700 !important;
    color: #111827 !important;
}
div[data-testid="column"] {
    padding-left: 0rem !important;
    padding-right: 0rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
_defaults = {
    'parsed_resumes': [],
    'candidates_df': None,
    'matched_results': None,
    'review_results': None,
    'selected_for_pool': set(),
    'resume_texts': {},
    'resume_metadata': {},
    'logged_in': False,
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
    # ── Login gate ─────────────────────────────────────────────────────────────
    if not render_login_page():
        return   # stop here — login page is shown, app body hidden

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
        render_user_badge()
        st.title("⚙️ Settings")

        st.subheader("🛡️ Privacy")
        st.markdown(
            "<div style='background:#FEF3C7; border:1px solid #F59E0B; border-radius:8px; "
            "padding:10px 12px; font-size:0.88rem; color:#92400E;'>"
            "⚠️ <strong>PII Masking is always ON</strong><br>"
            "<span style='font-size:0.82rem;'>Personal details (email, phone) are always "
            "redacted before AI processing.</span>"
            "</div>",
            unsafe_allow_html=True
        )
        mask_pii_enabled = True  # always enforced — not user-configurable

        st.divider()

        sp_connected_flag   = st.session_state.get('sharepoint_config', {}).get('connected', False)
        sp_selected_in_tab1 = st.session_state.get('upload_method_radio', '') == "☁️ Retrieve from SharePoint"
        sp_active = sp_connected_flag and sp_selected_in_tab1

        st.subheader("☁️ SharePoint Date Filter")
        if sp_active:
            st.markdown(
                "<ul style='font-size:0.88rem; color:#555; margin:0 0 8px 0; padding-left:16px; line-height:1.9;'>"
                "<li>Applies to SharePoint resumes only</li>"
                "<li>Filters by upload date to SharePoint</li>"
                "</ul>",
                unsafe_allow_html=True
            )
            use_date_filter = st.checkbox(
                "Turn on date filter",
                value=False,
                key="date_filter_checkbox"
            )
        else:
            st.markdown(
                "<div style='background:#F1F5F9; border-radius:8px; padding:10px 14px; "
                "color:#94A3B8; font-size:0.88rem;'>"
                "🔒 Available only when <strong>Retrieve from SharePoint</strong> "
                "is selected in the Upload tab."
                "</div>",
                unsafe_allow_html=True
            )
            use_date_filter = False

        start_date = end_date = None
        if use_date_filter:
            col_from, col_to = st.columns(2)
            with col_from:
                start_date = st.date_input(
                    "From",
                    value=datetime.now().date() - timedelta(days=90),
                    key="date_from"
                )
            with col_to:
                end_date = st.date_input(
                    "To",
                    value=datetime.now().date(),
                    key="date_to"
                )
            if start_date and end_date:
                if start_date > end_date:
                    st.error("⚠️ 'From' date cannot be after 'To' date.")
                    start_date = end_date = None
                else:
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