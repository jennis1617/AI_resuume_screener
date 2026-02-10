"""
UI Tab rendering functions
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from utils.file_handlers import extract_text_from_file
from utils.preprocessing import parse_resume_with_groq, extract_jd_requirements
from utils.scoring import (
    match_candidates_with_jd,
    auto_pre_screen_candidates,
    generate_interview_questions,
    format_strengths_weaknesses,
    format_dataframe_for_display
)
from utils.sharepoint import (
    connect_to_sharepoint,
    upload_to_sharepoint,
    download_from_sharepoint,
    save_csv_to_sharepoint,
    SHAREPOINT_AVAILABLE,
    SHAREPOINT_ERROR
)
from config.settings import JD_TEMPLATES

def render_upload_tab():
    """Render the Upload Resumes tab"""
    st.header("Step 1: Upload & Parse Resumes")
    
    # Get configuration from session state
    client = st.session_state.get('client')
    mask_pii_enabled = st.session_state.get('mask_pii_enabled', True)
    
    upload_method = st.radio(
        "Choose upload method:",
        ["📁 Manual Upload", "☁️ SharePoint Integration"],
        horizontal=True
    )
    
    if upload_method == "☁️ SharePoint Integration":
        st.subheader("SharePoint Configuration")
        
        if not SHAREPOINT_AVAILABLE:
            st.error("⚠️ SharePoint libraries not available.")
            
            if SHAREPOINT_ERROR:
                with st.expander("📋 Error Details"):
                    st.code(SHAREPOINT_ERROR)
            
            st.info("💡 **Solution:** Restart your Streamlit server after installing the library")
            st.code("# Stop Streamlit (Ctrl+C), then:\npip install Office365-REST-Python-Client\nstreamlit run app.py", language="bash")
            
            if st.button("🔄 Recheck Library Availability"):
                st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1:
                sharepoint_url = st.text_input(
                    "SharePoint Site URL", 
                    value=st.session_state.sharepoint_config.get('site_url', ''),
                    placeholder="https://yourcompany.sharepoint.com/sites/HR"
                )
                username = st.text_input(
                    "Username",
                    value=st.session_state.sharepoint_config.get('username', ''),
                    placeholder="user@company.com"
                )
            with col2:
                folder_path = st.text_input(
                    "Folder Path", 
                    value=st.session_state.sharepoint_config.get('folder_path', ''),
                    placeholder="/Shared Documents/Resumes"
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter password"
                )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔗 Connect to SharePoint", type="primary"):
                    if sharepoint_url and username and password and folder_path:
                        with st.spinner("Connecting to SharePoint..."):
                            ctx = connect_to_sharepoint(sharepoint_url, username, password)
                            if ctx:
                                st.session_state.sharepoint_config = {
                                    'site_url': sharepoint_url,
                                    'username': username,
                                    'password': password,
                                    'folder_path': folder_path,
                                    'connected': True,
                                    'context': ctx
                                }
                                st.success("✅ Connected to SharePoint successfully!")
                    else:
                        st.error("Please fill in all SharePoint credentials")
            
            with col2:
                if st.session_state.sharepoint_config.get('connected'):
                    st.success("✅ SharePoint Connected")
            
            if st.session_state.sharepoint_config.get('connected'):
                st.divider()
                
                sharepoint_action = st.radio(
                    "Choose SharePoint action:",
                    ["📥 Download Resumes from SharePoint", "📤 Upload Resumes to SharePoint"],
                    horizontal=True
                )
                
                if sharepoint_action == "📥 Download Resumes from SharePoint":
                    if st.button("📥 Download All Resumes", type="primary"):
                        with st.spinner("Downloading resumes from SharePoint..."):
                            ctx = st.session_state.sharepoint_config['context']
                            folder_path = st.session_state.sharepoint_config['folder_path']
                            
                            downloaded_files = download_from_sharepoint(ctx, folder_path)
                            
                            if downloaded_files and client:
                                st.success(f"✅ Downloaded {len(downloaded_files)} files from SharePoint")
                                
                                # Parse downloaded files
                                progress = st.progress(0)
                                status = st.empty()
                                
                                st.session_state.parsed_resumes = []
                                st.session_state.resume_texts = {}
                                st.session_state.resume_metadata = {}
                                
                                for idx, file_data in enumerate(downloaded_files):
                                    status.text(f"Processing: {file_data['name']}")
                                    
                                    text = extract_text_from_file(file_data)
                                    
                                    if text:
                                        # Use SharePoint timestamp
                                        upload_date = file_data.get('timestamp', datetime.now().isoformat())
                                        if isinstance(upload_date, str):
                                            try:
                                                upload_date = datetime.fromisoformat(upload_date.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M:%S")
                                            except:
                                                upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        
                                        parsed = parse_resume_with_groq(client, text, file_data['name'], mask_pii_enabled, upload_date)
                                        if parsed:
                                            st.session_state.parsed_resumes.append(parsed)
                                            st.session_state.resume_texts[parsed.get('name', '')] = text
                                            st.session_state.resume_metadata[parsed.get('name', '')] = {
                                                'submission_date': upload_date,
                                                'filename': file_data['name']
                                            }
                                    
                                    progress.progress((idx + 1) / len(downloaded_files))
                                
                                status.empty()
                                progress.empty()
                                
                                if st.session_state.parsed_resumes:
                                    st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                                    st.success(f"✅ Successfully parsed {len(st.session_state.parsed_resumes)} resumes from SharePoint!")
                
                else:  # Upload to SharePoint
                    st.info("📤 Upload resumes manually first, then they will be saved to SharePoint")
                    
                    uploaded_files_sp = st.file_uploader(
                        "Upload Resumes to SharePoint",
                        type=['pdf', 'docx'],
                        accept_multiple_files=True,
                        help="Upload resumes to save to SharePoint",
                        key="sharepoint_upload"
                    )
                    
                    if uploaded_files_sp:
                        if st.button("📤 Upload to SharePoint", type="primary"):
                            ctx = st.session_state.sharepoint_config['context']
                            folder_path = st.session_state.sharepoint_config['folder_path']
                            
                            success_count = 0
                            for file in uploaded_files_sp:
                                file_content = file.read()
                                file.seek(0)  # Reset file pointer
                                
                                if upload_to_sharepoint(ctx, folder_path, file_content, file.name):
                                    success_count += 1
                            
                            if success_count > 0:
                                st.success(f"✅ Successfully uploaded {success_count}/{len(uploaded_files_sp)} files to SharePoint!")
    
    else:
        # Manual Upload - ONLY PDF and DOCX
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_files = st.file_uploader(
                "Upload Resumes",
                type=['pdf', 'docx'],
                accept_multiple_files=True,
                help="Upload resumes in PDF or DOCX format only"
            )
        with col2:
            st.metric("📁 Uploaded", len(uploaded_files) if uploaded_files else 0)
            st.metric("✅ Parsed", len(st.session_state.parsed_resumes))
        
        if uploaded_files and client:
            if st.button("🚀 Parse All Resumes", type="primary"):
                progress = st.progress(0)
                status = st.empty()
                
                st.session_state.parsed_resumes = []
                st.session_state.resume_texts = {}
                st.session_state.resume_metadata = {}
                
                for idx, file in enumerate(uploaded_files):
                    status.text(f"Processing: {file.name}")
                    
                    text = extract_text_from_file(file)
                    
                    if text:
                        # Get file upload date with timestamp
                        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        parsed = parse_resume_with_groq(client, text, file.name, mask_pii_enabled, upload_date)
                        if parsed:
                            st.session_state.parsed_resumes.append(parsed)
                            st.session_state.resume_texts[parsed.get('name', '')] = text
                            st.session_state.resume_metadata[parsed.get('name', '')] = {
                                'submission_date': upload_date,
                                'filename': file.name
                            }
                    
                    progress.progress((idx + 1) / len(uploaded_files))
                
                status.empty()
                progress.empty()
                
                if st.session_state.parsed_resumes:
                    st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                    st.success(f"✅ Successfully parsed {len(st.session_state.parsed_resumes)} resumes!")
                    
                    # Option to save to SharePoint
                    if st.session_state.sharepoint_config.get('connected'):
                        if st.button("💾 Save to SharePoint"):
                            ctx = st.session_state.sharepoint_config['context']
                            folder_path = st.session_state.sharepoint_config['folder_path']
                            
                            # Upload original files
                            for file in uploaded_files:
                                file_content = file.read()
                                file.seek(0)
                                upload_to_sharepoint(ctx, folder_path, file_content, file.name)
                            
                            # Save parsed data CSV
                            csv_filename = f"parsed_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            if save_csv_to_sharepoint(ctx, folder_path, st.session_state.candidates_df, csv_filename):
                                st.success("✅ Resumes and parsed data saved to SharePoint!")
                    
                    csv_buffer = io.StringIO()
                    st.session_state.candidates_df.to_csv(csv_buffer, index=False)
                    
                    st.download_button(
                        "💾 Download Parsed Data (CSV)",
                        csv_buffer.getvalue(),
                        f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )
        
        if st.session_state.parsed_resumes:
            st.subheader("Recently Parsed Resumes (Preview)")
            for resume in st.session_state.parsed_resumes[:3]:
                with st.expander(f"👤 {resume.get('name', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Experience:** {resume.get('experience_years')} years")
                        st.write(f"**Email:** {resume.get('email')}")
                        st.write(f"**Submitted:** {resume.get('submission_date', 'N/A')}")
                    with col2:
                        st.write(f"**Current Role:** {resume.get('current_role')}")
                        st.write(f"**Skills:** {resume.get('tech_stack', '')[:80]}...")

def render_database_tab():
    """Render the Candidate Pool tab"""
    from config.settings import COLUMN_DISPLAY_NAMES
    
    st.header("Candidate Database")
    
    # Get configuration
    use_date_filter = st.session_state.get('use_date_filter', False)
    start_date = st.session_state.get('start_date')
    end_date = st.session_state.get('end_date')
    
    if st.session_state.candidates_df is not None:
        df = st.session_state.candidates_df.copy()
        
        # Apply date filter if enabled
        if use_date_filter and start_date and end_date:
            try:
                df['submission_date'] = pd.to_datetime(df['submission_date'])
                df = df[(df['submission_date'].dt.date >= start_date) & (df['submission_date'].dt.date <= end_date)]
                st.info(f"📅 Showing {len(df)} resumes from {start_date} to {end_date}")
            except:
                pass
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Candidates", len(st.session_state.candidates_df))
        with col2:
            st.metric("In Date Range", len(df) if use_date_filter else len(st.session_state.candidates_df))
        with col3:
            avg_exp = df['experience_years'].astype(float).mean()
            st.metric("Average Experience", f"{avg_exp:.1f} years")
        
        st.divider()
        
        # Professional instruction box for column selection
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; 
                    border-radius: 10px; 
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color: white; margin: 0 0 10px 0; font-size: 1.3rem;">
                🔍 Customize Your Candidate View
            </h3>
            <p style="color: #f0f0f0; margin: 0; font-size: 1rem; line-height: 1.5;">
                Select the columns below to filter and customize your candidate pool display. 
                Choose the data fields most relevant to your screening process.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Dynamically set default columns based on what exists
        available_cols = list(df.columns)
        default_cols = [col for col in ['name', 'email', 'experience_years', 'tech_stack', 'current_role', 'submission_date'] 
                    if col in available_cols]
        
        # Create reverse mapping for selection
        reverse_mapping = {v: k for k, v in COLUMN_DISPLAY_NAMES.items()}
        
        # Get display names for available columns
        available_display_names = [COLUMN_DISPLAY_NAMES.get(col, col) for col in available_cols]
        default_display_names = [COLUMN_DISPLAY_NAMES.get(col, col) for col in default_cols]
        
        # Column selector with user-friendly names
        selected_display_names = st.multiselect(
            "Select columns to display:",
            available_display_names,
            default=default_display_names if default_display_names else available_display_names[:min(5, len(available_display_names))]
        )
        
        # Convert back to original column names
        display_cols = [reverse_mapping.get(name, name) for name in selected_display_names]
        
        if display_cols:
            # Format dataframe for better display
            formatted_df = format_dataframe_for_display(df, display_cols)
            st.dataframe(formatted_df, use_container_width=True, height=400, hide_index=True)
        
        if not df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                st.download_button(
                    "📥 Download Database (CSV)",
                    csv_buffer.getvalue(),
                    f"candidate_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
            
            with col2:
                if st.session_state.sharepoint_config.get('connected'):
                    if st.button("☁️ Save Database to SharePoint"):
                        ctx = st.session_state.sharepoint_config['context']
                        folder_path = st.session_state.sharepoint_config['folder_path']
                        csv_filename = f"candidate_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        
                        if save_csv_to_sharepoint(ctx, folder_path, df, csv_filename):
                            st.success("✅ Database saved to SharePoint!")
    else:
        st.info("📤 Please upload and parse resumes in the 'Upload Resumes' tab first")

def render_matching_tab():
    """Render the AI Matching tab"""
    st.header("Step 2: AI-Powered Candidate Matching")
    
    # Get configuration
    client = st.session_state.get('client')
    top_n = st.session_state.get('top_n', 5)
    use_date_filter = st.session_state.get('use_date_filter', False)
    start_date = st.session_state.get('start_date')
    end_date = st.session_state.get('end_date')
    
    if st.session_state.candidates_df is not None:
        # JD Upload
        st.subheader("📌 Job Description Input")
        jd_input_mode = st.radio(
            "Choose input method:",
            ["Paste Text", "Upload File (PDF/DOCX)"],
            horizontal=True
        )
        
        job_desc = ""
        
        if jd_input_mode == "Upload File (PDF/DOCX)":
            jd_file = st.file_uploader(
                "Upload Job Description",
                type=['pdf', 'docx'],
                key="jd_upload"
            )
            if jd_file:
                jd_text = extract_text_from_file(jd_file)
                if jd_text:
                    job_desc = jd_text
                    st.success("✅ Job description loaded successfully!")
                    with st.expander("Preview Job Description"):
                        st.text(job_desc[:500] + "..." if len(job_desc) > 500 else job_desc)
        else:
            jd_template = st.selectbox(
                "Quick Template (Optional)",
                ["Custom", "Senior Python Developer", "Data Scientist", "DevOps Engineer"]
            )
            
            job_desc = st.text_area(
                "Job Description",
                value=JD_TEMPLATES.get(jd_template, ""),
                height=300,
                placeholder="Paste or type the complete job description here..."
            )
        
        if job_desc and client:
            st.divider()
            
            # AUTOMATED REQUIREMENT EXTRACTION
            st.subheader("Automated Pre-Screening")
            
            if st.button("Analyze JD & Match Candidates", type="primary", use_container_width=True):
                with st.spinner("Analyzing job requirements..."):
                    # Extract requirements from JD
                    jd_requirements = extract_jd_requirements(client, job_desc)
                    
                    if jd_requirements:
                        st.success("✅ Job requirements extracted successfully!")
                        
                        # Display extracted requirements
                        with st.expander("📋 Extracted Requirements from Job Description", expanded=True):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Job Title:** {jd_requirements.get('job_title', 'N/A')}")
                                st.write(f"**Seniority Level:** {jd_requirements.get('seniority_level', 'N/A')}")
                                st.write(f"**Minimum Experience:** {jd_requirements.get('minimum_experience_years', 0)} years")
                            with col2:
                                st.write(f"**Required Skills:** {', '.join(jd_requirements.get('required_technical_skills', []))}")
                                if jd_requirements.get('preferred_skills'):
                                    st.write(f"**Preferred Skills:** {', '.join(jd_requirements.get('preferred_skills', []))}")
                        
                        # Apply automated pre-screening
                        with st.spinner("Pre-screening candidates based on job requirements..."):
                            # Apply date filter if enabled
                            df_to_screen = st.session_state.candidates_df.copy()
                            if use_date_filter and start_date and end_date:
                                try:
                                    df_to_screen['submission_date'] = pd.to_datetime(df_to_screen['submission_date'])
                                    df_to_screen = df_to_screen[(df_to_screen['submission_date'].dt.date >= start_date) & 
                                                                (df_to_screen['submission_date'].dt.date <= end_date)]
                                except:
                                    pass
                            
                            filtered_df, screening_summary = auto_pre_screen_candidates(df_to_screen, jd_requirements)
                            
                            if screening_summary:
                                st.info("**Automated Pre-Screening Results:**")
                                for summary in screening_summary:
                                    st.write(summary)
                            
                            # Display pre-screened candidates in a proper table
                            if not filtered_df.empty:
                                st.subheader("✅ Pre-Screened Candidates")
                                
                                # Select columns for pre-screened display
                                prescreened_cols = ['name', 'email', 'experience_years', 'tech_stack', 'current_role']
                                available_prescreened_cols = [col for col in prescreened_cols if col in filtered_df.columns]
                                
                                # Format and display
                                formatted_prescreened = format_dataframe_for_display(filtered_df, available_prescreened_cols)
                                st.dataframe(formatted_prescreened, use_container_width=True, hide_index=True, height=300)
                                
                                # Download pre-screened candidates
                                csv_buffer = io.StringIO()
                                filtered_df.to_csv(csv_buffer, index=False)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.download_button(
                                        "📥 Download Pre-Screened Candidates (CSV)",
                                        csv_buffer.getvalue(),
                                        f"prescreened_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                        "text/csv"
                                    )
                                
                                with col2:
                                    if st.session_state.sharepoint_config.get('connected'):
                                        if st.button("☁️ Save to SharePoint"):
                                            ctx = st.session_state.sharepoint_config['context']
                                            folder_path = st.session_state.sharepoint_config['folder_path']
                                            csv_filename = f"prescreened_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                            
                                            if save_csv_to_sharepoint(ctx, folder_path, filtered_df, csv_filename):
                                                st.success("✅ Pre-screened candidates saved to SharePoint!")
                                
                                # Proceed with AI matching
                                with st.spinner(f"AI is analyzing top {top_n} candidates..."):
                                    results = match_candidates_with_jd(client, filtered_df, job_desc, top_n)
                                    
                                    if results:
                                        st.session_state.matched_results = results
                                        st.success(f"✅ Successfully ranked {len(results)} top candidates!")
                            else:
                                st.warning("⚠️ No candidates passed the automated pre-screening criteria. Consider adjusting the job requirements or uploading more resumes.")
        
        # Display matched results
        if st.session_state.matched_results:
            st.divider()
            st.subheader(f"🏆 Top {len(st.session_state.matched_results)} Recommended Candidates")
            
            for cand in st.session_state.matched_results:
                rank = cand.get('rank', 0)
                name = cand.get('name', 'Unknown')
                email = cand.get('email', 'N/A')
                match = cand.get('match_percentage', 0)
                semantic_score = cand.get('semantic_score', 0)
                final_score = cand.get('final_score', match)
                strengths = cand.get('strengths', 'N/A')
                gaps = cand.get('gaps', 'N/A')
                rec = cand.get('recommendation', 'N/A')
                priority = cand.get('interview_priority', 'Medium')
                
                # Color coding based on final score
                if final_score >= 80:
                    color = "#28a745"
                elif final_score >= 60:
                    color = "#ffc107"
                else:
                    color = "#dc3545"
                
                st.markdown(f"""
                <div style="border-left: 5px solid {color}; padding: 20px; margin: 15px 0; background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h3>#{rank} - {name} <span style="float: right; color: {color}; font-size: 1.8rem;">{final_score}%</span></h3>
                    <p style="font-size: 1.0rem; color: #555; margin-top: 5px;">📧 {email}</p>
                    <p style="font-size: 1.1rem;"><strong>🎯 {rec}</strong> | <strong>⚡ Interview Priority: {priority}</strong></p>
                    <p style="font-size: 0.95em; color: #666; margin-top: 10px;">
                        <strong>AI Match Score:</strong> {match}% | <strong>Resume-JD Compatibility:</strong> {semantic_score}%
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Format strengths and weaknesses as bullet points
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**✅ Key Strengths:**")
                    strength_items = format_strengths_weaknesses(strengths)
                    if strength_items:
                        for item in strength_items:
                            st.markdown(f'<div class="strength-item">• {item}</div>', unsafe_allow_html=True)
                    else:
                        st.write("No specific strengths listed")
                
                with col2:
                    st.markdown("**⚠️ Areas for Consideration:**")
                    weakness_items = format_strengths_weaknesses(gaps)
                    if weakness_items and gaps != "None":
                        for item in weakness_items:
                            st.markdown(f'<div class="weakness-item">• {item}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="strength-item">• No significant gaps identified</div>', unsafe_allow_html=True)
                
                # Full profile
                cand_full = st.session_state.candidates_df[
                    st.session_state.candidates_df['name'] == name
                ]
                
                if not cand_full.empty:
                    cand_data = cand_full.iloc[0].to_dict()
                    
                    with st.expander(f"📋 View Complete Profile - {name}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**📧 Email:** {cand_data.get('email')}")
                            st.write(f"**📱 Phone:** {cand_data.get('phone')}")
                            st.write(f"**💼 Experience:** {cand_data.get('experience_years')} years")
                            st.write(f"**📅 Resume Received:** {cand_data.get('submission_date', 'N/A')}")
                        with col2:
                            st.write(f"**🎯 Current Role:** {cand_data.get('current_role')}")
                            st.write(f"**🎓 Education:** {cand_data.get('education')}")
                            st.write(f"**🏆 Certifications:** {cand_data.get('certifications', 'None')}")
                        
                        st.write(f"**💻 Technical Skills:** {cand_data.get('tech_stack')}")
                        st.write(f"**🚀 Key Projects:** {cand_data.get('key_projects')}")
                        
                        if st.button(f"🎤 Generate Interview Questions", key=f"q_{rank}"):
                            with st.spinner("Generating personalized interview questions..."):
                                questions = generate_interview_questions(client, cand_data, job_desc)
                                
                                if questions:
                                    st.markdown("---")
                                    st.subheader(f"Interview Questions for {name}")
                                    for idx, q in enumerate(questions, 1):
                                        st.markdown(f"""
                                        **Question {idx} ({q.get('category')}):**  
                                        {q.get('question')}  
                                        *💡 Why we're asking: {q.get('why_asking')}*
                                        """)
                                        st.divider()
                
                st.markdown("---")
            
            # Download matched results
            results_df = pd.DataFrame(st.session_state.matched_results)
            
            col1, col2 = st.columns(2)
            
            with col1:
                csv_buffer = io.StringIO()
                results_df.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    "📊 Download Matching Results (CSV)",
                    csv_buffer.getvalue(),
                    f"top_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                if st.session_state.sharepoint_config.get('connected'):
                    if st.button("☁️ Save Matching Results to SharePoint", use_container_width=True):
                        ctx = st.session_state.sharepoint_config['context']
                        folder_path = st.session_state.sharepoint_config['folder_path']
                        csv_filename = f"top_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        
                        if save_csv_to_sharepoint(ctx, folder_path, results_df, csv_filename):
                            st.success("✅ Matching results saved to SharePoint!")
    else:
        st.info("📤 Please upload and parse resumes in the 'Upload Resumes' tab first")

def render_analytics_tab():
    """Render the Analytics Dashboard tab"""
    st.header("📈 Recruitment Analytics Dashboard")
    
    # Get configuration
    use_date_filter = st.session_state.get('use_date_filter', False)
    start_date = st.session_state.get('start_date')
    end_date = st.session_state.get('end_date')
    
    if st.session_state.candidates_df is not None:
        df = st.session_state.candidates_df.copy()
        
        # Apply date filter if enabled
        if use_date_filter and start_date and end_date:
            try:
                df['submission_date'] = pd.to_datetime(df['submission_date'])
                df = df[(df['submission_date'].dt.date >= start_date) & (df['submission_date'].dt.date <= end_date)]
            except:
                pass
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_exp = df['experience_years'].astype(float).mean()
            st.metric("Average Experience", f"{avg_exp:.1f} years")
        with col2:
            st.metric("Total Candidate Pool", len(df))
        with col3:
            if st.session_state.matched_results:
                avg_match = sum(c['final_score'] for c in st.session_state.matched_results) / len(st.session_state.matched_results)
                st.metric("Avg Compatibility Score", f"{avg_match:.1f}%")
            else:
                st.metric("Avg Compatibility Score", "N/A")
        with col4:
            unique_skills = len(set(', '.join(df['tech_stack'].astype(str)).split(', ')))
            st.metric("Unique Skills in Pool", unique_skills)
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Experience Distribution")
            exp_bins = pd.cut(df['experience_years'].astype(float), 
                             bins=[0, 2, 5, 10, 20], 
                             labels=['0-2 years', '2-5 years', '5-10 years', '10+ years'])
            exp_counts = exp_bins.value_counts().sort_index()
            
            fig = px.bar(
                x=exp_counts.index.astype(str), 
                y=exp_counts.values, 
                labels={'x': 'Experience Range', 'y': 'Number of Candidates'},
                color=exp_counts.values,
                color_continuous_scale='Blues'
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if st.session_state.matched_results:
                st.subheader("Candidate Compatibility Scores")
                scores = [c['final_score'] for c in st.session_state.matched_results]
                names = [c['name'] for c in st.session_state.matched_results]
                
                fig = go.Figure(data=[go.Bar(
                    x=scores,
                    y=names,
                    orientation='h',
                    marker=dict(
                        color=scores,
                        colorscale='RdYlGn',
                        showscale=True
                    ),
                    text=[f"{s}%" for s in scores],
                    textposition='outside'
                )])
                fig.update_layout(
                    xaxis_title="Compatibility Score (%)",
                    yaxis_title="Candidate",
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Run AI matching to see compatibility scores")
        
        # Top Skills Chart - ENHANCED with better hover widget
        st.subheader("Top Skills in Candidate Pool")
        
        # Create skill-to-candidates mapping
        skill_candidates = {}
        for idx, row in df.iterrows():
            skills = str(row.get('tech_stack', '')).lower().split(',')
            candidate_name = row.get('name', 'Unknown')
            for skill in skills:
                skill = skill.strip()
                if skill and skill != 'nan':
                    if skill not in skill_candidates:
                        skill_candidates[skill] = []
                    skill_candidates[skill].append(candidate_name)
        
        # Count and sort skills
        skill_counts = {skill: len(candidates) for skill, candidates in skill_candidates.items()}
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        
        skill_names = [s[0].title() for s in sorted_skills]
        skill_values = [s[1] for s in sorted_skills]
        
        # Create ENHANCED hover text with better formatting
        hover_texts = []
        for skill_name in [s[0] for s in sorted_skills]:
            candidates = skill_candidates[skill_name]
            # Format candidates in a readable way
            if len(candidates) <= 8:
                candidates_list = '<br>   • '.join(candidates)
                hover_text = f"<b>Candidates with this skill:</b><br>   • {candidates_list}"
            else:
                candidates_list = '<br>   • '.join(candidates[:8])
                hover_text = f"<b>Candidates with this skill:</b><br>   • {candidates_list}<br>   • ...and {len(candidates)-8} more"
            hover_texts.append(hover_text)
        
        fig = go.Figure(data=[go.Bar(
            y=skill_names[::-1],  # Reverse to show top at top
            x=skill_values[::-1],
            orientation='h',
            marker=dict(
                color=skill_values[::-1],
                colorscale='Viridis',
                showscale=False
            ),
            text=skill_values[::-1],
            textposition='outside',
            hovertext=hover_texts[::-1],
            hovertemplate='<b style="font-size:16px">%{y}</b><br>Count: %{x}<br><br>%{hovertext}<extra></extra>'
        )])
        
        fig.update_layout(
            xaxis_title="Number of Candidates",
            yaxis_title="Skill",
            height=600,
            margin=dict(l=150),
            hoverlabel=dict(
                bgcolor="white",
                font_size=14,
                font_family="Arial",
                font_color="black",
                bordercolor="gray"
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Resume Submission Timeline (if date data available)
        if 'submission_date' in df.columns:
            st.subheader("Resume Submission Timeline")
            try:
                df['submission_date'] = pd.to_datetime(df['submission_date'])
                timeline = df.groupby(df['submission_date'].dt.date).size().reset_index()
                timeline.columns = ['Date', 'Count']
                
                fig = px.line(
                    timeline, 
                    x='Date', 
                    y='Count',
                    markers=True,
                    labels={'Count': 'Resumes Received'}
                )
                fig.update_layout(
                    hovermode='x unified',
                    hoverlabel=dict(
                        bgcolor="white",
                        font_size=14,
                        font_family="Arial"
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                pass
        
    else:
        st.info("📤 Please upload and parse resumes to view analytics")