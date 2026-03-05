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
Sign in to your account
 
"""
Candidate Review & Scoring Tab — updated per mentor review:
1. AI-only scoring (no hybrid/semantic) using llama-3.3-70b-versatile
2. Candidates sorted highest score first
3. Info bubble rewritten as short bullet points
4. Button renamed to 'Run AI Screening'
5. Quality check: green/yellow only (no red)
6. Areas of knowledge removed
7. Word doc + PPT buttons per candidate card
8. Spinner shows 'Adding [name] to Candidate Pool...' on checkbox
"""
 
import json
from datetime import datetime
import streamlit as st
import pandas as pd
from utils.resume_analysis import ResumeAnalyzer
from utils.file_handlers import extract_text_from_file
from utils.resume_formatter import (
    extract_detailed_resume_data,
    check_template_completeness,
    generate_resume_docx,
)
from utils.ppt_generator import generate_candidate_ppt
from utils.template_mapper import map_to_template_format
from utils.sharepoint import (
    SHAREPOINT_AVAILABLE,
    upload_jd_to_sharepoint,
    list_jds_from_sharepoint,
    download_jd_from_sharepoint,
    delete_jd_from_sharepoint,
    list_resumes_by_uploader,
)
 
 
def render_analysis_tab(parsed_resumes, client):
    st.header("🎯 Candidate Review & Scoring")
 
    # ── Info bubble — concise bullet points ──────────────────────────────────
    st.markdown("""
    <div style="background:#F0F7FF; padding:16px 22px; border-radius:10px;
                border-left:5px solid #4A90D9; margin-bottom:24px;">
        <p style="color:#1A5276; margin:0 0 8px 0; font-size:1.05rem; font-weight:700;">
            How this works
        </p>
        <ul style="color:#2C3E50; margin:0; padding-left:18px;
                   font-size:0.95rem; line-height:1.85;">
            <li>Paste or upload the <strong>Job Description</strong> below</li>
            <li>Click <strong>Run AI Screening</strong> — AI scores every resume against the job</li>
            <li>Results appear ranked by score, <strong>highest first</strong></li>
            <li>☑️ Select candidates at your discretion for <strong>interview consideration</strong></li>
            <li>📋 AI generates a <strong>NexTurn-compatible</strong> structured profile document per candidate</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
 
    # ── Job Description Input ─────────────────────────────────────────────────
    st.subheader("📄 Step 1 — Enter the Job Details")
 
    sp_connected = st.session_state.get('sharepoint_config', {}).get('connected', False)
 
    jd_source_options = ["Upload a file (PDF or Word)"]
    if sp_connected:
        jd_source_options.append("Load from SharePoint")
 
    jd_mode = st.radio(
        "How would you like to provide the job details?",
        jd_source_options,
        horizontal=True,
        key="review_jd_mode"
    )
 
    job_desc = ""
 
    if jd_mode == "Upload a file (PDF or Word)":
        jd_file = st.file_uploader(
            "Upload job description", type=['pdf', 'docx'], key="review_jd_upload"
        )
        if jd_file:
            job_desc = extract_text_from_file(jd_file)
            if job_desc:
                st.success("✅ Job description loaded successfully!")
                with st.expander("Preview what was loaded"):
                    st.text(job_desc[:600] + ("…" if len(job_desc) > 600 else ""))
 
    elif jd_mode == "Load from SharePoint":
        _render_sharepoint_jd_panel()
        job_desc = st.session_state.get("active_jd_text", "")
 
    # ── Save current JD to SharePoint ─────────────────────────────────────────
    if job_desc and job_desc.strip() and sp_connected:
        with st.expander("☁️ Save this JD to SharePoint"):
            jd_name = st.text_input(
                "File name for this JD",
                value="JD_" + datetime.now().strftime("%Y%m%d_%H%M") + ".txt",
                key="jd_save_name"
            )
            if st.button("💾 Save JD to SharePoint", key="save_jd_btn"):
                sp = st.session_state.sharepoint_config
                if upload_jd_to_sharepoint(sp, job_desc, jd_name):
                    st.success(f"✅ JD saved to SharePoint as **{jd_name}**")
 
    if not job_desc or not job_desc.strip():
        st.info("👆 Please enter a job description above to continue.")
        return
 
    st.divider()
 
    # ── Launch button ─────────────────────────────────────────────────────────
    st.subheader("Step 2 — Run AI Screening")
 
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        run_review = st.button(
            "Run AI Screening",
            type="primary",
            use_container_width=True
        )
    with col_info:
        st.markdown(
            f"<p style='color:#555; padding-top:10px;'>"
            f"AI will screen <strong>{len(parsed_resumes)}</strong> candidates "
            f"against this job description.</p>",
            unsafe_allow_html=True
        )
 
    if run_review:
        _run_full_analysis(parsed_resumes, client, job_desc)
 
    if 'selected_for_pool' not in st.session_state:
        st.session_state.selected_for_pool = set()
 
    if st.session_state.get('review_results'):
        _render_results(client)
 
 
 
def _render_sharepoint_jd_panel():
    """
    Shows all JDs saved in SharePoint.
    - My JDs: uploaded by the current logged-in user
    - All JDs: every JD in the folder
    HR can load a JD, or delete one (with confirmation pop-up).
    """
    sp = st.session_state.get('sharepoint_config', {})
    current_user = st.session_state.get('current_user_name', '')
 
    with st.spinner("Loading JDs from SharePoint…"):
        all_jds = list_jds_from_sharepoint(sp)
 
    if not all_jds:
        st.info("No job descriptions found in SharePoint yet. Save one using the option below.")
        return
 
    # Split into mine vs others
    my_jds    = [j for j in all_jds if j['created_by'].lower() == current_user.lower()] if current_user else []
    other_jds = [j for j in all_jds if j not in my_jds]
 
    # ── My JDs dropdown ───────────────────────────────────────────────────────
    st.markdown("**📂 My JDs** *(uploaded by you)*")
    if my_jds:
        my_names = [j['name'] for j in my_jds]
        sel_my = st.selectbox("Select one of your JDs to load",
                              ["— select —"] + my_names, key="sp_my_jd_select")
        if sel_my != "— select —":
            jd_obj = next(j for j in my_jds if j['name'] == sel_my)
            if st.button("📥 Load this JD", key="load_my_jd"):
                text = download_jd_from_sharepoint(jd_obj['download_url'])
                if text:
                    st.session_state['active_jd_text'] = text
                    st.success(f"✅ Loaded: {sel_my}")
    else:
        st.caption("You haven't uploaded any JDs yet.")
 
    st.divider()
 
    # ── All available JDs dropdown ────────────────────────────────────────────
    st.markdown("**☁️ All Available JDs** *(from SharePoint)*")
    if other_jds:
        other_names = [j['name'] for j in other_jds]
        sel_other = st.selectbox("Select a JD to load",
                                 ["— select —"] + other_names, key="sp_other_jd_select")
        if sel_other != "— select —":
            jd_obj = next(j for j in other_jds if j['name'] == sel_other)
            col_load, col_del = st.columns([1, 1])
            with col_load:
                if st.button("📥 Load this JD", key="load_other_jd"):
                    text = download_jd_from_sharepoint(jd_obj['download_url'])
                    if text:
                        st.session_state['active_jd_text'] = text
                        st.success(f"✅ Loaded: {sel_other}")
            with col_del:
                if st.button("🗑️ Delete this JD", key="del_other_jd", type="secondary"):
                    st.session_state['_jd_pending_delete'] = jd_obj
                    st.rerun()
    else:
        st.caption("No other JDs in SharePoint.")
 
    # ── Delete confirmation pop-up ────────────────────────────────────────────
    if st.session_state.get('_jd_pending_delete'):
        jd_to_del = st.session_state['_jd_pending_delete']
        st.warning(
            f"⚠️ Are you sure you want to **permanently delete** "
            f"**{jd_to_del['name']}** from SharePoint? This cannot be undone."
        )
        col_yes, col_no, _ = st.columns([1, 1, 3])
        with col_yes:
            if st.button("✅ Yes, delete it", key="confirm_del_jd", type="primary"):
                if delete_jd_from_sharepoint(sp, jd_to_del['item_id']):
                    st.success(f"✅ Deleted: {jd_to_del['name']}")
                del st.session_state['_jd_pending_delete']
                st.rerun()
        with col_no:
            if st.button("❌ Cancel", key="cancel_del_jd"):
                del st.session_state['_jd_pending_delete']
                st.rerun()
 
    # Show currently loaded JD preview
    if st.session_state.get('active_jd_text'):
        with st.expander("Preview loaded JD"):
            st.text(st.session_state['active_jd_text'][:600] + "…")
 
 
def _run_full_analysis(parsed_resumes, client, job_desc):
    """Score every candidate with AI only. Sort by score descending."""
    st.session_state.review_results = []
    st.session_state.selected_for_pool = set()
    st.session_state.review_job_desc = job_desc
 
    analyzer = ResumeAnalyzer(client)
    res_list = parsed_resumes if isinstance(parsed_resumes, list) else [parsed_resumes]
 
    progress   = st.progress(0)
    status_box = st.empty()
    raw_results = []
 
    for idx, res_data in enumerate(res_list):
        name = res_data.get('name', f"Candidate {idx + 1}")
        status_box.markdown(
            f"<p style='color:#555;'> AI screening "
            f"<strong>{name}</strong> ({idx + 1}/{len(res_list)})…</p>",
            unsafe_allow_html=True
        )
 
        resume_text = st.session_state.get('resume_texts', {}).get(name, str(res_data))
 
        analysis = analyzer.analyze_resume(resume_text)
        for key in ['career_gaps', 'technical_anomalies', 'fake_indicators', 'domain_knowledge']:
            raw = analysis.get(key, [])
            if isinstance(raw, list):
                analysis[key] = [
                    str(item.get('description', item) if isinstance(item, dict) else item)
                    for item in raw
                ]
            else:
                analysis[key] = [str(raw)] if raw else []
 
        ai_score, breakdown, reason = _score_single(client, res_data, job_desc)
 
        raw_results.append({
            "metadata":    res_data,
            "analysis":    analysis,
            "final_score": ai_score,
            "breakdown":   breakdown,
            "reason":      reason,
        })
 
        progress.progress((idx + 1) / len(res_list))
 
    status_box.empty()
    progress.empty()
 
    # Sort highest first
    raw_results.sort(key=lambda x: x['final_score'], reverse=True)
    st.session_state.review_results = raw_results
 
    st.success(f"✅ AI screening complete — {len(res_list)} candidates ranked by match score.")
 
 
def _render_results(client):
    results  = st.session_state.review_results
    selected = st.session_state.selected_for_pool
 
    st.divider()
 
    total  = len(results)
    chosen = len(selected)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Candidates", total)
    c2.metric("Added to Pool",    chosen)
    c3.metric("Still to Review",  total - chosen)
 
    col_sel, col_desel, _ = st.columns([1, 1, 3])
    with col_sel:
        if st.button("✅ Select All", use_container_width=True):
            st.session_state.selected_for_pool = {
                r['metadata'].get('name', f"Candidate_{i}") for i, r in enumerate(results)
            }
            st.rerun()
    with col_desel:
        if st.button("☐ Clear All", use_container_width=True):
            st.session_state.selected_for_pool = set()
            st.rerun()
 
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"📋 All {total} Candidates — ranked by AI score")
 
    # ── Pre-generate docs silently for all candidates so download is 1-click ──
    for idx, item in enumerate(results):
        name = item['metadata'].get('name', f"Candidate_{idx + 1}")
        doc_key = f"docx_bytes_{name}"
        ppt_key = f"pptx_bytes_{name}"
        det_key = f"detailed_{name}"
        if doc_key not in st.session_state or ppt_key not in st.session_state:
            resume_text = st.session_state.get('resume_texts', {}).get(name, str(item['metadata']))
            if det_key not in st.session_state:
                try:
                    st.session_state[det_key] = extract_detailed_resume_data(
                        client, resume_text, item['metadata']
                    )
                except Exception:
                    st.session_state[det_key] = item['metadata']
            detailed = st.session_state[det_key]
            if doc_key not in st.session_state:
                try:
                    st.session_state[doc_key] = generate_resume_docx(detailed)
                except Exception:
                    st.session_state[doc_key] = None
            if ppt_key not in st.session_state:
                try:
                    mapped = map_to_template_format(detailed)
                    st.session_state[ppt_key] = generate_candidate_ppt({**detailed, **mapped})
                except Exception:
                    st.session_state[ppt_key] = None
 
    for idx, item in enumerate(results):
        meta        = item['metadata']
        analysis    = item['analysis']
        final_score = item.get('final_score', 0)
        name        = meta.get('name', f"Candidate_{idx + 1}")
        is_selected = name in selected
 
        selected_tag  = "☑ Added to Pool" if is_selected else "☐ Not Selected"
        expander_title = f"#{idx + 1}  {name}  |  🎯 {final_score}% match  |  {selected_tag}"
 
        # ── Checkbox OUTSIDE expander so HR can select without opening card ──
        col_chk, col_card = st.columns([0.01, 0.99])
        with col_chk:
            checked = st.checkbox(
                f"Select {name}",
                value=is_selected,
                key=f"chk_{idx}",
                help=f"Add {name} to the Candidate Pool",
                label_visibility="collapsed",
            )
            if checked and name not in st.session_state.selected_for_pool:
                with st.spinner(f"Adding {name} to Candidate Pool…"):
                    st.session_state.selected_for_pool.add(name)
                st.rerun()
            elif not checked and name in st.session_state.selected_for_pool:
                st.session_state.selected_for_pool.discard(name)
                st.rerun()
 
        with col_card:
            with st.expander(expander_title, expanded=(idx == 0 and not is_selected)):
 
                st.markdown("<br>", unsafe_allow_html=True)
 
                _render_score_section(meta, final_score,
                                         item.get("breakdown", {}),
                                         item.get("reason", ""))
                st.markdown("<br>", unsafe_allow_html=True)
                _render_quality_section(analysis)
                st.markdown("<br>", unsafe_allow_html=True)
                _render_doc_buttons(client, name, meta, idx)
 
    if selected:
        st.divider()
        st.success(
            f"**{len(selected)}** candidate(s) in pool. "
            "Go to the **Candidate Pool** tab to view the shortlist."
        )
 
 
def _render_score_section(meta, final_score, breakdown=None, reason=""):
    st.markdown("#### 🎯 AI Match Score")
 
    if final_score >= 75:
        bg, border, fg = "#E8F5E9", "#A5D6A7", "#2E7D32"
    elif final_score >= 50:
        bg, border, fg = "#E3F2FD", "#90CAF9", "#1565C0"
    else:
        bg, border, fg = "#FFFDE7", "#FFE082", "#E65100"
 
    col_details, col_score = st.columns([2, 1])
 
    with col_details:
        for label, value in [
            ("📧 Email",        meta.get('email', 'Not provided')),
            ("📱 Phone",        meta.get('phone', 'Not provided')),
            ("💼 Experience",   f"{meta.get('experience_years', '?')} years"),
            ("🎯 Current Role", meta.get('current_role', 'Not specified')),
            ("💻 Key Skills",   str(meta.get('tech_stack', 'N/A'))[:130]),
        ]:
            st.markdown(
                f"<p style='font-size:1.05rem; margin:6px 0;'>"
                f"<strong>{label}:</strong> {value}</p>",
                unsafe_allow_html=True
            )
 
    with col_score:
        st.markdown(f"""
        <div style="text-align:center; background:{bg};
                    border:2px solid {border}; border-radius:14px; padding:22px 12px;">
            <div style="font-size:0.82rem; color:#666; margin-bottom:6px; font-weight:500;">
                AI Match Score
            </div>
            <div style="font-size:2.4rem; font-weight:700; color:{fg};">
                {final_score}%
            </div>
        </div>
        """, unsafe_allow_html=True)
 
    # Score breakdown chart
    if breakdown:
        _render_score_breakdown(final_score, breakdown, reason)
 
 
def _render_score_breakdown(final_score, breakdown, reason):
    """
    Visual bar chart — each bar rendered with its own st.markdown call
    so Streamlit does not escape the HTML content.
    """
    weights = {
        "Skills Match":       "40% weight",
        "Experience Match":   "30% weight",
        "Projects Match":     "20% weight",
        "Domain & Education": "10% weight",
    }
 
    # ── Container header ─────────────────────────────────────────────────────
    st.markdown(
        f"""<div style="background:#F9FAFB; border:1px solid #E5E7EB;
                border-radius:12px; padding:20px 22px 6px 22px; margin-top:18px;">
            <p style="font-size:1rem; font-weight:700; color:#111827; margin:0 0 16px 0;">
                📊 Score Breakdown — why this candidate scored
                <strong>{final_score}%</strong>
            </p>
        </div>""",
        unsafe_allow_html=True
    )
 
    # ── One st.markdown per bar so Streamlit renders it properly ─────────────
    for dim, score in breakdown.items():
        weight_label = weights.get(dim, "")
        pct = max(0, min(100, score))
        if pct >= 70:
            bar_colour = "#4CAF50"
        elif pct >= 45:
            bar_colour = "#FF9800"
        else:
            bar_colour = "#F44336"
 
        st.markdown(
            f"""<div style="background:#F9FAFB; padding:0 22px 14px 22px;">
                <div style="display:flex; justify-content:space-between;
                            align-items:baseline; margin-bottom:5px;">
                    <span style="font-size:0.97rem; font-weight:600; color:#1F2937;">
                        {dim}
                    </span>
                    <span style="font-size:0.85rem; color:#6B7280;">
                        {weight_label} &nbsp;&middot;&nbsp;
                        <strong style="color:#111;">{pct}%</strong>
                    </span>
                </div>
                <div style="background:#E5E7EB; border-radius:999px;
                            height:14px; width:100%;">
                    <div style="background:{bar_colour}; width:{pct}%;
                                height:14px; border-radius:999px;">
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True
        )
 
    # ── Why this score reason ─────────────────────────────────────────────────
    if reason:
        st.markdown(
            f"""<div style="background:#F9FAFB; padding:0 22px 10px 22px;">
                <div style="padding:10px 14px; background:#F0F9FF;
                            border-left:4px solid #3B82F6; border-radius:6px;
                            font-size:0.93rem; color:#1E40AF;">
                    💡 <strong>Why this score?</strong> {reason}
                </div>
            </div>""",
            unsafe_allow_html=True
        )
 
    # ── Formula footnote + close container ───────────────────────────────────
    st.markdown(
        """<div style="background:#F9FAFB; padding:4px 22px 18px 22px;
                border-radius:0 0 12px 12px; border:1px solid #E5E7EB;
                border-top:none;">
            <p style="font-size:1rem; font-weight:600; color:#374151; margin:0;">
                Final score = Skills&times;40% + Experience&times;30%
                + Projects&times;20% + Domain&times;10%
            </p>
        </div>""",
        unsafe_allow_html=True
    )
 
 
def _render_quality_section(analysis):
    """Green / Yellow only — red removed. Areas of knowledge removed."""
    st.markdown("---")
    st.markdown("#### 📋 Resume Quality Check")
 
    if analysis.get('is_previous_employee'):
        st.info(f"ℹ️ **Worked at NexTurn before:** {analysis.get('nexturn_history_details', 'Yes')}")
 
    def green_box(label, msg):
        st.markdown(f"""
        <div style="background:#F0FFF4; border:1px solid #86EFAC; border-radius:8px;
                    padding:10px 14px; margin-bottom:8px;">
            <span style="color:#166534; font-weight:600;">✅ {label}:</span>
            <span style="color:#166534;"> {msg}</span>
        </div>""", unsafe_allow_html=True)
 
    def yellow_bullets(label, items):
        """Always render as bullet list — one point per line, no run-on sentences."""
        import re
        # Each item from the list may itself be a long sentence — split further
        # on ". Capital" or ", Capital" patterns to get atomic points
        atomic = []
        for raw in items:
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', str(raw).strip())
            for p in parts:
                p = p.strip().rstrip('. ')
                if p:
                    atomic.append(p)
 
        if not atomic:
            return
 
        if len(atomic) == 1:
            # Single short point — show inline
            st.markdown(
                f'''<div style="background:#FFFDE7; border:1px solid #FDD835;
                        border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                    <span style="color:#856404; font-weight:600;">⚠️ {label}:</span>
                    <span style="color:#5D4037;"> {atomic[0]}</span>
                </div>''', unsafe_allow_html=True
            )
        else:
            li_html = "".join(
                f'<li style="margin-bottom:5px; line-height:1.5;">{p}</li>'
                for p in atomic
            )
            st.markdown(
                f'''<div style="background:#FFFDE7; border:1px solid #FDD835;
                        border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                    <span style="color:#856404; font-weight:600;">⚠️ {label}:</span>
                    <ul style="color:#5D4037; margin:7px 0 0 0; padding-left:20px;">
                        {li_html}
                    </ul>
                </div>''', unsafe_allow_html=True
            )
 
    gaps = analysis.get('career_gaps', [])
    if gaps:
        yellow_bullets("Gaps in work history", gaps)
    else:
        green_box("Work history", "No major gaps found")
 
    tech_issues = analysis.get('technical_anomalies', [])
    if tech_issues:
        yellow_bullets("Things to double-check", tech_issues)
    else:
        green_box("Experience details", "Everything looks consistent")
 
    concerns = analysis.get('fake_indicators', [])
    if concerns:
        yellow_bullets("Points that need a closer look", concerns)
 
    # Areas of knowledge — removed per mentor request
 
 
def _render_doc_buttons(client, name, meta, idx):
    """NexTurn Profile Export — single-click download (pre-generated on load)."""
    st.markdown("#### 📋 NexTurn Profile Export")
 
    safe    = name.replace(' ', '_').replace('/', '_')
    doc_key = f"docx_bytes_{name}"
    ppt_key = f"pptx_bytes_{name}"
 
    col_word, col_ppt = st.columns(2)
 
    with col_word:
        docx_bytes = st.session_state.get(doc_key)
        if docx_bytes:
            st.download_button(
                "⬇️ Download Word Doc",
                data=docx_bytes,
                file_name=f"{safe}_resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"dl_word_{idx}"
            )
        else:
            st.caption("⏳ Word doc generating…")
 
    with col_ppt:
        pptx_bytes = st.session_state.get(ppt_key)
        if pptx_bytes:
            st.download_button(
                "⬇️ Download PPT Profile",
                data=pptx_bytes,
                file_name=f"{safe}_profile.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
                key=f"dl_ppt_{idx}"
            )
        else:
            st.caption("⏳ PPT generating…")
 
 
def _score_single(client, candidate_data: dict, job_desc: str) -> tuple:
    """
    AI-only scoring using llama-3.3-70b-versatile.
    Upgraded from 8b-instant because the AI score now carries 100% weight.
    """
    from utils.groq_client import create_groq_completion
    fallback_client = st.session_state.get('fallback_client')
 
    summary = (
        f"Name: {candidate_data.get('name', 'N/A')}\n"
        f"Experience: {candidate_data.get('experience_years', 'N/A')} years\n"
        f"Skills: {candidate_data.get('tech_stack', 'N/A')}\n"
        f"Current Role: {candidate_data.get('current_role', 'N/A')}\n"
        f"Education: {candidate_data.get('education', 'N/A')}\n"
        f"Projects: {str(candidate_data.get('key_projects', ''))[:400]}\n"
        f"Certifications: {candidate_data.get('certifications', 'None')}"
    )
 
    prompt = (
        "You are an expert technical recruiter. Score this candidate against the job description "
        "on a scale of 0–100. Be accurate and critical — do not inflate scores.\n\n"
        f"JOB DESCRIPTION:\n{job_desc[:2000]}\n\n"
        f"CANDIDATE:\n{summary}\n\n"
        "Score each dimension 0-100. Be accurate, do not inflate scores.\n"
        "Dimensions: skills_match (40%), experience_match (30%), "
        "projects_match (20%), domain_match (10%).\n"
        "Also give a one-sentence reason for the overall score.\n\n"
        'Return ONLY JSON: {"skills_match":<0-100>,"experience_match":<0-100>,'
        '"projects_match":<0-100>,"domain_match":<0-100>,"overall":<0-100>,"reason":"<sentence>"}'
    )
 
    try:
        resp = create_groq_completion(
            client, fallback_client,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a precise recruiter scoring assistant. Return only valid JSON."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        raw  = resp.choices[0].message.content.strip()
        j    = raw.find('{')
        data = json.loads(raw[j:raw.rfind('}') + 1])
        bd = {
            "Skills Match":       max(0, min(100, int(data.get("skills_match", 0)))),
            "Experience Match":   max(0, min(100, int(data.get("experience_match", 0)))),
            "Projects Match":     max(0, min(100, int(data.get("projects_match", 0)))),
            "Domain & Education": max(0, min(100, int(data.get("domain_match", 0)))),
        }
        overall = max(0, min(100, int(data.get("overall", 0))))
        if overall == 0:
            overall = round(bd["Skills Match"]*0.4 + bd["Experience Match"]*0.3
                            + bd["Projects Match"]*0.2 + bd["Domain & Education"]*0.1)
        return overall, bd, str(data.get("reason", ""))
    except Exception:
        return 0, {}, ""
 
"""
UI Tab rendering functions - Upload and Analytics only.
Candidate Review & Scoring is in ui/analysis_tab.py
Candidate Pool is in ui/candidate_pool_tab.py
"""
 
import streamlit as st
import pandas as pd
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
 
from utils.file_handlers import extract_text_from_file
from utils.preprocessing import parse_resume_with_groq
from utils.scoring import format_dataframe_for_display
from utils.sharepoint import (
    SHAREPOINT_AVAILABLE,
    download_from_sharepoint,
    save_csv_to_sharepoint,
)
from config.settings import COLUMN_DISPLAY_NAMES
 
 
def _sp_config():
    return st.session_state.get('sharepoint_config', {})
 
 
def _sp_connected():
    return _sp_config().get('connected', False)
 
 
# ── Upload Tab ─────────────────────────────────────────────────────────────────
 
def render_upload_tab():
    """Render the Upload Resumes tab"""
    st.header("Step 1: Upload/Retrieve Resumes")
 
    client = st.session_state.get('client')
    mask_pii_enabled = st.session_state.get('mask_pii_enabled', True)
 
    upload_method = st.radio(
        "Where are the resumes coming from?",
        ["📁 Upload Manually", "☁️ Retrieve from SharePoint"],
        horizontal=True,
        key="upload_method_radio",
    )
    # Store so sidebar can check whether SharePoint is currently selected
    st.session_state['upload_method'] = upload_method
 
    # ── SharePoint ─────────────────────────────────────────────────────────────
    if upload_method == "☁️ Retrieve from SharePoint":
        st.subheader("SharePoint")
 
        if not SHAREPOINT_AVAILABLE:
            st.error("⚠️ The SharePoint connection library is not installed. Run `pip install msal`.")
            return
 
        if not _sp_connected():
            st.warning("⚠️ SharePoint is not connected. Please set up your credentials in the sidebar.")
            return
 
        st.success("✅ SharePoint Connected")
 
        if st.button("📥 Get All Resumes from SharePoint", type="primary"):
            with st.spinner("Fetching resumes…"):
                sp = _sp_config()
                downloaded_files = download_from_sharepoint(sp)
 
                if downloaded_files and client:
                    st.success(f"✅ Found {len(downloaded_files)} files in SharePoint")
                    progress = st.progress(0)
                    status = st.empty()
 
                    st.session_state.parsed_resumes = []
                    st.session_state.resume_texts = {}
                    st.session_state.resume_metadata = {}
 
                    seen_candidate_names = set()
 
                    for idx, file_data in enumerate(downloaded_files):
                        status.text(f"Reading: {file_data['name']}")
                        text = extract_text_from_file(file_data)
                        if text:
                            upload_date = file_data.get('timestamp', datetime.now().isoformat())
                            if isinstance(upload_date, str):
                                try:
                                    upload_date = datetime.fromisoformat(
                                        upload_date.replace('Z', '+00:00')
                                    ).strftime("%Y-%m-%d %H:%M:%S")
                                except Exception:
                                    upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            parsed = parse_resume_with_groq(
                                client, text, file_data['name'], mask_pii_enabled, upload_date
                            )
                            if parsed:
                                candidate_name = parsed.get('name', '').strip().lower()
                                if candidate_name and candidate_name in seen_candidate_names:
                                    progress.progress((idx + 1) / len(downloaded_files))
                                    continue
                                if candidate_name:
                                    seen_candidate_names.add(candidate_name)
                                st.session_state.parsed_resumes.append(parsed)
                                st.session_state.resume_texts[parsed.get('name', '')] = text
                                st.session_state.resume_metadata[parsed.get('name', '')] = {
                                    'submission_date': upload_date,
                                    'filename': file_data['name'],
                                }
                        progress.progress((idx + 1) / len(downloaded_files))
 
                    status.empty()
                    progress.empty()
 
                    if st.session_state.parsed_resumes:
                        st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                        st.success(
                            f"📥 Received {len(st.session_state.parsed_resumes)} resumes — "
                            "Go to **Candidate Review & Scoring** to continue."
                        )
                elif not downloaded_files:
                    st.warning("No PDF or Word files found in the configured SharePoint folder.")
 
    # ── Manual Upload ──────────────────────────────────────────────────────────
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_files = st.file_uploader(
                "Upload Resumes (PDF or Word files only)",
                type=['pdf', 'docx'],
                accept_multiple_files=True,
                help="Upload as many resumes as you need. PDF and Word formats are supported.",
            )
        with col2:
            st.metric("📁 Files Selected", len(uploaded_files) if uploaded_files else 0)
            # Use a placeholder so the metric updates immediately after parsing
            resumes_ready_placeholder = st.empty()
            resumes_ready_placeholder.metric(
                "✅ Resumes Ready", len(st.session_state.parsed_resumes)
            )
 
        if uploaded_files and client:
            if st.button("Read All Resumes", type="primary"):
                progress = st.progress(0)
                status = st.empty()
 
                st.session_state.parsed_resumes = []
                st.session_state.resume_texts = {}
                st.session_state.resume_metadata = {}
 
                for idx, file in enumerate(uploaded_files):
                    status.text(f"Reading: {file.name}")
                    text = extract_text_from_file(file)
                    if text:
                        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        parsed = parse_resume_with_groq(
                            client, text, file.name, mask_pii_enabled, upload_date
                        )
                        if parsed:
                            st.session_state.parsed_resumes.append(parsed)
                            st.session_state.resume_texts[parsed.get('name', '')] = text
                            st.session_state.resume_metadata[parsed.get('name', '')] = {
                                'submission_date': upload_date,
                                'filename': file.name,
                            }
                    progress.progress((idx + 1) / len(uploaded_files))
 
                status.empty()
                progress.empty()
 
                if st.session_state.parsed_resumes:
                    st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                    # Refresh the metric immediately with the new count
                    resumes_ready_placeholder.metric(
                        "✅ Resumes Ready", len(st.session_state.parsed_resumes)
                    )
                    st.success(
                        f"📥 Received {len(st.session_state.parsed_resumes)} resumes — "
                        "Go to the **Candidate Review & Scoring** tab to continue."
                    )
 
        if st.session_state.parsed_resumes:
            st.subheader("Resumes Loaded (Quick Preview)")
            for resume in st.session_state.parsed_resumes[:3]:
                with st.expander(f"👤 {resume.get('name', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Experience:** {resume.get('experience_years')} years")
                        st.write(f"**Email:** {resume.get('email')}")
                        st.write(f"**Received:** {resume.get('submission_date', 'N/A')}")
                    with col2:
                        st.write(f"**Current Role:** {resume.get('current_role')}")
                        st.write(f"**Skills:** {str(resume.get('tech_stack', ''))[:80]}…")
 
 
# ── Analytics Tab ──────────────────────────────────────────────────────────────
 
def render_analytics_tab():
    """Render the Analytics Dashboard tab"""
    st.header("📈 Analytics Dashboard")
 
    use_date_filter = st.session_state.get('use_date_filter', False)
    start_date = st.session_state.get('start_date')
    end_date = st.session_state.get('end_date')
 
    if st.session_state.candidates_df is not None:
        df = st.session_state.candidates_df.copy()
 
        if use_date_filter and start_date and end_date:
            try:
                df['submission_date'] = pd.to_datetime(df['submission_date'])
                df = df[
                    (df['submission_date'].dt.date >= start_date) &
                    (df['submission_date'].dt.date <= end_date)
                ]
            except Exception:
                pass
 
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Resumes Uploaded", len(df))
        with col2:
            selected = st.session_state.get('selected_for_pool', set())
            st.metric("In Candidate Pool", len(selected))
        with col3:
            unique_skills = len(set(', '.join(df['tech_stack'].astype(str)).split(', ')))
            st.metric("Different Skills Seen", unique_skills)
 
        st.divider()
 
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Experience Levels")
            exp_bins = pd.cut(
                pd.to_numeric(df['experience_years'], errors='coerce').fillna(0),
                bins=[0, 2, 5, 10, 20],
                labels=['0–2 years', '2–5 years', '5–10 years', '10+ years'],
            )
            exp_counts = exp_bins.value_counts().sort_index()
            fig = px.bar(
                x=exp_counts.index.astype(str),
                y=exp_counts.values,
                labels={'x': 'Experience Level', 'y': 'Number of People'},
                color=exp_counts.values,
                color_continuous_scale='Blues',
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
 
        with col2:
            review_results = st.session_state.get('review_results')
            if review_results:
                st.subheader("Match Scores")
                scores = [r['final_score'] for r in review_results]
                names = [r['metadata'].get('name', '?') for r in review_results]
                fig = go.Figure(data=[go.Bar(
                    x=scores, y=names, orientation='h',
                    marker=dict(
                        color=scores,
                        colorscale=[[0, '#FFCDD2'], [0.5, '#FFE082'], [1, '#C8E6C9']],
                        showscale=True,
                        colorbar=dict(title="Score"),
                    ),
                    text=[f"{s}%" for s in scores],
                    textposition='outside',
                )])
                fig.update_layout(
                    xaxis_title="Match Score (%)",
                    yaxis_title="Candidate",
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Run a review in the Candidate Review & Scoring tab to see match scores here.")
 
        st.subheader("Most Common Skills")
        skill_candidates = {}
        for _, row in df.iterrows():
            skills = str(row.get('tech_stack', '')).lower().split(',')
            candidate_name = row.get('name', 'Unknown')
            for skill in skills:
                skill = skill.strip()
                if skill and skill != 'nan':
                    skill_candidates.setdefault(skill, []).append(candidate_name)
 
        total_candidates = len(df)
        skill_counts = {skill: len(cands) for skill, cands in skill_candidates.items()}
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15]
 
        if sorted_skills:
            skill_names = [s[0].title() for s in sorted_skills]
            skill_percentages = [(s[1] / total_candidates * 100) for s in sorted_skills]
 
            hover_texts = []
            for i, skill_name in enumerate([s[0] for s in sorted_skills]):
                candidates = skill_candidates[skill_name]
                pct = skill_percentages[i]
                count = skill_counts[skill_name]
                if len(candidates) <= 8:
                    clist = '<br>   • '.join(candidates)
                    hover_texts.append(
                        f"<b>{skill_name.title()}</b><br><br><b>How common:</b> {pct:.1f}% "
                        f"({count}/{total_candidates})<br><br><b>Candidates:</b><br>   • {clist}"
                    )
                else:
                    clist = '<br>   • '.join(candidates[:8])
                    hover_texts.append(
                        f"<b>{skill_name.title()}</b><br><br><b>How common:</b> {pct:.1f}% "
                        f"({count}/{total_candidates})<br><br><b>Candidates:</b><br>   • {clist}"
                        f"<br>   • …and {len(candidates) - 8} more"
                    )
 
            fig = go.Figure(data=[go.Bar(
                y=skill_names[::-1], x=skill_percentages[::-1], orientation='h',
                marker=dict(
                    color=skill_percentages[::-1], colorscale='Tealgrn', showscale=True,
                    colorbar=dict(title="% of Candidates", titleside="right", ticksuffix="%"),
                ),
                text=[f"{p:.1f}%" for p in skill_percentages[::-1]],
                textposition='outside',
                hovertext=hover_texts[::-1],
                hovertemplate='%{hovertext}<extra></extra>',
            )])
            fig.update_layout(
                xaxis_title="Percentage of Candidates (%)",
                yaxis_title="Skill",
                height=600,
                margin=dict(l=150),
                hoverlabel=dict(bgcolor="white", font_size=15, font_family="Arial",
                                font_color="black", bordercolor="#BDBDBD", align="left"),
            )
            st.plotly_chart(fig, use_container_width=True)
 
        if 'submission_date' in df.columns:
            st.subheader("When Resumes Were Received")
            try:
                df['submission_date'] = pd.to_datetime(df['submission_date'])
                timeline = df.groupby(df['submission_date'].dt.date).size().reset_index()
                timeline.columns = ['Date', 'Count']
                fig = px.line(timeline, x='Date', y='Count', markers=True,
                              labels={'Count': 'Resumes Received'})
                fig.update_traces(line_color='#64B5F6', marker=dict(size=8, color='#42A5F5'))
                fig.update_layout(hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass
 
    else:
        st.info("📤 Please upload and process resumes first to see analytics.")
 