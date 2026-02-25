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
        ["📁 Upload from my computer", "☁️ Retrieve from SharePoint"],
        horizontal=True,
    )

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

                    seen_candidate_names = set()  # deduplicate by extracted name

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
                                # Skip if we already have a resume for this candidate name
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
                "✅ Resumes Received", len(st.session_state.parsed_resumes)
            )

        if uploaded_files and client:
            if st.button("🚀 Read All Resumes", type="primary"):
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
                        "✅ Resumes Received", len(st.session_state.parsed_resumes)
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