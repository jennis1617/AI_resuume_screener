"""
AI-Powered Resume Screening System
Built with Groq for Ultra-Fast LLM Processing

"""

import streamlit as st
import pandas as pd
import json
import os
import re
from groq import Groq
from datetime import datetime
import io
from typing import List, Dict
import PyPDF2
import docx2txt
import plotly.express as px
import plotly.graph_objects as go
import pytesseract
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Page Configuration
st.set_page_config(
    page_title="AI Resume Screening System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: black;
        text-align: center;
        padding: 20px 0;
    }
    .sub-header {
        text-align: center;
        color: #555;
        font-size: 1.2rem;
        margin-bottom: 30px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'parsed_resumes' not in st.session_state:
    st.session_state.parsed_resumes = []
if 'candidates_df' not in st.session_state:
    st.session_state.candidates_df = None
if 'matched_results' not in st.session_state:
    st.session_state.matched_results = None
if 'resume_texts' not in st.session_state:
    st.session_state.resume_texts = {}

# Groq Client
@st.cache_resource
def init_groq_client(api_key):
    return Groq(api_key=api_key)

# PII Masking
def mask_pii(text):
    """Redacts PII before sending to LLM."""
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

# Extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

# Extract text from DOCX
def extract_text_from_docx(docx_file):
    try:
        text = docx2txt.process(docx_file)
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return ""

# OCR Support
def extract_text_from_image(image_file):
    """Extracts text from images using OCR."""
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error reading image with OCR: {str(e)}")
        return ""

#  Extract text with OCR support
def extract_text_from_file(uploaded_file):
    """Extract text from PDF, DOCX, or Images."""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if file_ext == 'pdf':
        return extract_text_from_pdf(uploaded_file)
    elif file_ext == 'docx':
        return extract_text_from_docx(uploaded_file)
    elif file_ext in ['png', 'jpg', 'jpeg']:
        return extract_text_from_image(uploaded_file)
    else:
        return ""

# TF-IDF Semantic Scoring
def calculate_semantic_score(resume_text, jd_text):
    """Calculate objective similarity score using TF-IDF."""
    try:
        vectorizer = TfidfVectorizer(max_features=500)
        vectors = vectorizer.fit_transform([resume_text, jd_text])
        score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return round(score * 100, 2)
    except:
        return 0

# Parse resume with optional PII masking
def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled=False):
    # Apply PII masking if enabled
    processed_text = mask_pii(resume_text) if mask_pii_enabled else resume_text
    
    prompt = f"""You are an expert AI resume parser. Extract structured data from this resume.

Return valid JSON with this exact structure:
{{
    "name": "full name",
    "email": "email or null",
    "phone": "phone or null",
    "experience_years": numeric value (e.g., 5.5),
    "tech_stack": "comma-separated skills (Python, AWS, Docker, etc)",
    "current_role": "most recent job title",
    "education": "highest degree",
    "key_projects": "brief summary of top achievements",
    "certifications": "certifications or null",
    "domain_expertise": "industry domain"
}}

Resume:
{processed_text[:6000]}

Return ONLY JSON, no markdown or extra text."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise resume parser. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1500
        )
        
        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            parsed_data = json.loads(response[json_start:json_end])
            parsed_data['filename'] = filename
            parsed_data['parsed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return parsed_data
        return None
            
    except Exception as e:
        st.error(f"Error parsing {filename}: {str(e)}")
        return None

# Pre-screening
def pre_screen_candidates(df, min_experience=0, required_skills=None):
    if df is None or df.empty:
        return df
    
    filtered_df = df.copy()
    
    if min_experience > 0:
        try:
            filtered_df['experience_years'] = pd.to_numeric(filtered_df['experience_years'], errors='coerce')
            filtered_df = filtered_df[filtered_df['experience_years'] >= min_experience]
        except:
            pass
    
    if required_skills:
        def has_skills(tech_stack):
            if pd.isna(tech_stack):
                return False
            return any(skill.lower() in str(tech_stack).lower() for skill in required_skills)
        
        filtered_df = filtered_df[filtered_df['tech_stack'].apply(has_skills)]
    
    return filtered_df

# Semantic matching with TF-IDF scoring
def match_candidates_with_jd(client, candidates_df, job_description, top_n=5):
    if candidates_df.empty:
        return []
    
    candidates_summary = ""
    for idx, row in candidates_df.iterrows():
        candidates_summary += f"""
Candidate {idx + 1}:
- Name: {row.get('name', 'N/A')}
- Experience: {row.get('experience_years', 'N/A')} years
- Tech Stack: {row.get('tech_stack', 'N/A')}
- Role: {row.get('current_role', 'N/A')}
- Projects: {row.get('key_projects', 'N/A')}
"""
    
    prompt = f"""You are an expert HR recruiter. Rank top {top_n} candidates for this job.

JOB DESCRIPTION:
{job_description}

CANDIDATES:
{candidates_summary}

Evaluate on: Technical skills (40%), Experience (30%), Projects (20%), Domain fit (10%)

Return JSON array:
[
  {{
    "rank": 1,
    "name": "Name",
    "match_percentage": 88,
    "strengths": "Top 3 strengths matching JD",
    "gaps": "Any concerns",
    "recommendation": "Strongly Recommended/Recommended/Consider/Not Recommended",
    "interview_priority": "High/Medium/Low"
  }}
]

Return ONLY JSON array."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Expert technical recruiter AI."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=3000
        )
        
        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        
        if json_start != -1:
            results = json.loads(response[json_start:json_end])
            
            # ADD TF-IDF SEMANTIC SCORES
            for result in results:
                candidate_name = result.get('name', '')
                # Get original resume text from session state
                resume_text = st.session_state.resume_texts.get(candidate_name, '')
                if resume_text:
                    semantic_score = calculate_semantic_score(resume_text, job_description)
                    result['semantic_score'] = semantic_score
                    # Blend LLM score (70%) + TF-IDF score (30%)
                    llm_score = result.get('match_percentage', 0)
                    result['final_score'] = round(llm_score * 0.7 + semantic_score * 0.3, 2)
                else:
                    result['semantic_score'] = 0
                    result['final_score'] = result.get('match_percentage', 0)
            
            return results
        return []
            
    except Exception as e:
        st.error(f"Matching error: {str(e)}")
        return []

# Generate interview questions
def generate_interview_questions(client, candidate_data, job_description):
    prompt = f"""Generate 8 targeted interview questions for this candidate.

CANDIDATE:
- Name: {candidate_data.get('name')}
- Experience: {candidate_data.get('experience_years')} years
- Tech: {candidate_data.get('tech_stack')}
- Role: {candidate_data.get('current_role')}

JOB: {job_description[:1000]}

Generate:
- 3 technical questions
- 2 behavioral (STAR format)
- 2 scenario-based
- 1 culture fit

Return JSON:
[{{"category": "Technical", "question": "...", "why_asking": "..."}}]"""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Interview question generator."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            max_tokens=2000
        )
        
        text = response.choices[0].message.content.strip()
        json_start = text.find('[')
        json_end = text.rfind(']') + 1
        
        if json_start != -1:
            return json.loads(text[json_start:json_end])
        return []
    except:
        return []

# Main App
def main():
    st.markdown('<h1 class="main-header">Resume Screening System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">⚡ Powered by Groq | Ultra-Fast AI Processing</p>', unsafe_allow_html=True)
    
    # Sidebar
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
        
        st.subheader("📊 Pre-Screening")
        min_experience = st.slider("Min Experience (years)", 0, 20, 0)
        
        required_skills_input = st.text_area(
            "Required Skills (one per line)",
            placeholder="Python\nAWS\nDocker",
            height=120
        )
        
        required_skills = [s.strip() for s in required_skills_input.split('\n') if s.strip()]
        
        if required_skills:
            st.info(f"🎯 Filtering: {', '.join(required_skills)}")
        
        st.divider()
        
        st.subheader("🎚️ Top Candidates")
        top_n = st.select_slider(
            "Select number",
            options=[1, 2, 3, 5, 10, 15, 20],
            value=5
        )
        
        if top_n <= 3:
            st.warning("⚡ Urgent Interview!")
        elif top_n <= 5:
            st.info("📅 Standard - 2 weeks")
        else:
            st.success("🕐 Flexible mode")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📊 Database", "🎯 Match", "📈 Analytics"])
    
    # TAB 1: Upload
    with tab1:
        st.header("Step 1: Upload & Parse (IDP)")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            # OCR Support - Added image formats
            uploaded_files = st.file_uploader(
                "Upload Resumes (PDF/DOCX/Images)",
                type=['pdf', 'docx', 'png', 'jpg', 'jpeg'],
                accept_multiple_files=True
            )
        with col2:
            st.metric("📁 Uploaded", len(uploaded_files) if uploaded_files else 0)
            st.metric("✅ Parsed", len(st.session_state.parsed_resumes))
        
        if uploaded_files and client:
            if st.button("🚀 Parse All", type="primary"):
                progress = st.progress(0)
                status = st.empty()
                
                st.session_state.parsed_resumes = []
                st.session_state.resume_texts = {}
                
                for idx, file in enumerate(uploaded_files):
                    status.text(f"Processing: {file.name}")
                    
                    # Use new extract_text_from_file function with OCR support
                    text = extract_text_from_file(file)
                    
                    if text:
                        # Pass PII masking flag
                        parsed = parse_resume_with_groq(client, text, file.name, mask_pii_enabled)
                        if parsed:
                            st.session_state.parsed_resumes.append(parsed)
                            # Store original text for TF-IDF scoring later
                            st.session_state.resume_texts[parsed.get('name', '')] = text
                    
                    progress.progress((idx + 1) / len(uploaded_files))
                
                status.empty()
                progress.empty()
                
                if st.session_state.parsed_resumes:
                    st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                    st.success(f"✅ Parsed {len(st.session_state.parsed_resumes)} resumes!")
                    
                    csv_buffer = io.StringIO()
                    st.session_state.candidates_df.to_csv(csv_buffer, index=False)
                    
                    st.download_button(
                        "💾 Download CSV",
                        csv_buffer.getvalue(),
                        f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )
        
        if st.session_state.parsed_resumes:
            st.subheader("Recently Parsed")
            for resume in st.session_state.parsed_resumes[:3]:
                with st.expander(f"👤 {resume.get('name', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Exp:** {resume.get('experience_years')} yrs")
                        st.write(f"**Email:** {resume.get('email')}")
                    with col2:
                        st.write(f"**Role:** {resume.get('current_role')}")
                        st.write(f"**Tech:** {resume.get('tech_stack', '')[:80]}...")
    
    # TAB 2: Database
    with tab2:
        st.header("Candidate Database")
        
        if st.session_state.candidates_df is not None:
            filtered_df = pre_screen_candidates(
                st.session_state.candidates_df,
                min_experience,
                required_skills
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total", len(st.session_state.candidates_df))
            with col2:
                st.metric("Pre-Screened", len(filtered_df))
            with col3:
                rate = (len(filtered_df) / len(st.session_state.candidates_df) * 100) if len(st.session_state.candidates_df) > 0 else 0
                st.metric("Pass Rate", f"{rate:.1f}%")
            
            st.divider()
            
            # Dynamically set default columns based on what exists
            available_cols = list(filtered_df.columns)
            default_cols = [col for col in ['name', 'experience_years', 'tech_stack', 'current_role'] 
                           if col in available_cols]
            
            display_cols = st.multiselect(
                "Columns",
                available_cols,
                default=default_cols if default_cols else available_cols[:min(4, len(available_cols))]
            )
            
            if display_cols:
                st.dataframe(filtered_df[display_cols], use_container_width=True, height=400)
            
            if not filtered_df.empty:
                csv_buffer = io.StringIO()
                filtered_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    "📥 Download Filtered",
                    csv_buffer.getvalue(),
                    f"filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
        else:
            st.info("Upload resumes first")
    
    # TAB 3: Matching
    with tab3:
        st.header("Step 3: Semantic Matching")
        
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
                        st.success("✅ JD loaded successfully!")
                        with st.expander("Preview JD"):
                            st.text(job_desc[:500] + "..." if len(job_desc) > 500 else job_desc)
            else:
                # Paste option
                jd_template = st.selectbox(
                    "Template",
                    ["Custom", "Senior Python Dev", "Data Scientist", "DevOps Engineer"]
                )
                
                templates = {
                    "Senior Python Dev": """Senior Python Developer - 5+ years

Required:
- 5+ years Python
- FastAPI/Django/Flask
- AWS (Lambda, EC2, S3)
- Docker, Kubernetes
- PostgreSQL/MongoDB
- CI/CD pipelines

Responsibilities:
- Design scalable backends
- Lead architecture
- Mentor developers
- Production deployment""",
                    
                    "Data Scientist": """Data Scientist - ML Focus

Required:
- 3+ years ML/AI
- Python (NumPy, Pandas, Scikit-learn)
- TensorFlow/PyTorch
- SQL, data warehousing
- Statistical analysis
- Gen AI experience (plus)

Responsibilities:
- Build ML models
- Large-scale data analysis
- A/B testing"""
                }
                
                job_desc = st.text_area(
                    "Job Description",
                    value=templates.get(jd_template, ""),
                    height=250
                )
            
            if job_desc and client:
                if st.button("🎯 Match Candidates", type="primary"):
                    with st.spinner("Analyzing..."):
                        filtered = pre_screen_candidates(
                            st.session_state.candidates_df,
                            min_experience,
                            required_skills
                        )
                        
                        if filtered.empty:
                            st.warning("No candidates passed pre-screening")
                        else:
                            results = match_candidates_with_jd(
                                client, filtered, job_desc, top_n
                            )
                            
                            if results:
                                st.session_state.matched_results = results
                                st.success(f"✅ Ranked {len(results)} candidates!")
            
            if st.session_state.matched_results:
                st.divider()
                st.subheader(f"🏆 Top {len(st.session_state.matched_results)} Candidates")
                
                for cand in st.session_state.matched_results:
                    rank = cand.get('rank', 0)
                    name = cand.get('name', 'Unknown')
                    match = cand.get('match_percentage', 0)
                    # Display TF-IDF scores
                    semantic_score = cand.get('semantic_score', 0)
                    final_score = cand.get('final_score', match)
                    strengths = cand.get('strengths', 'N/A')
                    gaps = cand.get('gaps', 'N/A')
                    rec = cand.get('recommendation', 'N/A')
                    priority = cand.get('interview_priority', 'Medium')
                    
                    color = "#28a745" if final_score >= 80 else "#ffc107" if final_score >= 60 else "#dc3545"
                    
                    st.markdown(f"""
                    <div style="border-left: 5px solid {color}; padding: 20px; margin: 15px 0; background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3>#{rank} - {name} <span style="float: right; color: {color};">{final_score}% Final Score</span></h3>
                        <p><strong>🎯 {rec}</strong> | <strong>⚡ Priority: {priority}</strong></p>
                        <p style="font-size: 0.9em; color: #666;">LLM Score: {match}% | TF-IDF Score: {semantic_score}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"**✅ Strengths:**\n{strengths}")
                    with col2:
                        if gaps and gaps != "None":
                            st.warning(f"**⚠️ Gaps:**\n{gaps}")
                    
                    cand_full = st.session_state.candidates_df[
                        st.session_state.candidates_df['name'] == name
                    ]
                    
                    if not cand_full.empty:
                        cand_data = cand_full.iloc[0].to_dict()
                        
                        with st.expander(f"📋 Full Profile - {name}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Email:** {cand_data.get('email')}")
                                st.write(f"**Phone:** {cand_data.get('phone')}")
                                st.write(f"**Exp:** {cand_data.get('experience_years')} yrs")
                            with col2:
                                st.write(f"**Role:** {cand_data.get('current_role')}")
                                st.write(f"**Education:** {cand_data.get('education')}")
                            
                            if st.button(f"🎤 Interview Questions", key=f"q_{rank}"):
                                with st.spinner("Generating..."):
                                    questions = generate_interview_questions(
                                        client, cand_data, job_desc
                                    )
                                    
                                    if questions:
                                        for q in questions:
                                            st.markdown(f"""
                                            **{q.get('category')}:** {q.get('question')}  
                                            *{q.get('why_asking')}*
                                            """)
                                            st.divider()
                    
                    st.divider()
                
                results_df = pd.DataFrame(st.session_state.matched_results)
                csv_buffer = io.StringIO()
                results_df.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    "📊 Download Results",
                    csv_buffer.getvalue(),
                    f"top_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
        else:
            st.info("Upload resumes first")
    
    # TAB 4: Analytics
    with tab4:
        st.header("📈 Analytics")
        
        if st.session_state.candidates_df is not None:
            df = st.session_state.candidates_df
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_exp = df['experience_years'].astype(float).mean()
                st.metric("Avg Experience", f"{avg_exp:.1f} yrs")
            with col2:
                st.metric("Total Pool", len(df))
            with col3:
                if st.session_state.matched_results:
                    avg_match = sum(c['final_score'] for c in st.session_state.matched_results) / len(st.session_state.matched_results)
                    st.metric("Avg Match", f"{avg_match:.1f}%")
                else:
                    st.metric("Avg Match", "N/A")
            with col4:
                unique_skills = len(set(', '.join(df['tech_stack'].astype(str)).split(', ')))
                st.metric("Unique Skills", unique_skills)
            
            st.divider()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Experience Distribution")
                exp_bins = pd.cut(df['experience_years'].astype(float), bins=[0, 2, 5, 10, 20], labels=['0-2', '2-5', '5-10', '10+'])
                exp_counts = exp_bins.value_counts().sort_index()
                
                fig = px.bar(x=exp_counts.index, y=exp_counts.values, color=exp_counts.values, color_continuous_scale='Blues')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if st.session_state.matched_results:
                    st.subheader("Match Scores")
                    scores = [c['final_score'] for c in st.session_state.matched_results]
                    fig = go.Figure(data=[go.Histogram(x=scores)])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Run matching to see scores")
            
            st.subheader("Top Skills")
            all_skills = ', '.join(df['tech_stack'].astype(str)).lower()
            skills = [s.strip() for s in all_skills.split(',')]
            skill_counts = pd.Series(skills).value_counts().head(15)
            
            fig = px.bar(x=skill_counts.values, y=skill_counts.index, orientation='h', color=skill_counts.values, color_continuous_scale='Viridis')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Upload resumes first")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🚀 AI Resume Screening System v1.0 | Built with Streamlit & Groq</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()