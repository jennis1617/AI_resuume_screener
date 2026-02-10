"""
Candidate scoring and matching utilities
"""

import streamlit as st
import pandas as pd
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def calculate_semantic_score(resume_text, jd_text):
    """Calculate objective similarity score using TF-IDF."""
    try:
        vectorizer = TfidfVectorizer(max_features=500)
        vectors = vectorizer.fit_transform([resume_text, jd_text])
        score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return round(score * 100, 2)
    except:
        return 0

def auto_pre_screen_candidates(df, jd_requirements):
    """Automatically pre-screen candidates based on JD requirements."""
    if df is None or df.empty or jd_requirements is None:
        return df, []
    
    filtered_df = df.copy()
    screening_summary = []
    
    # Filter by minimum experience
    min_exp = jd_requirements.get('minimum_experience_years', 0)
    if min_exp > 0:
        try:
            filtered_df['experience_years'] = pd.to_numeric(filtered_df['experience_years'], errors='coerce')
            before_count = len(filtered_df)
            filtered_df = filtered_df[filtered_df['experience_years'] >= min_exp]
            after_count = len(filtered_df)
            screening_summary.append(f"✓ Experience Filter: {min_exp}+ years → {after_count}/{before_count} candidates passed")
        except:
            pass
    
    # Filter by required skills - MORE FLEXIBLE MATCHING
    required_skills = jd_requirements.get('required_technical_skills', [])
    if required_skills:
        def has_required_skills(tech_stack):
            if pd.isna(tech_stack):
                return False
            tech_stack_lower = str(tech_stack).lower()
            
            # More flexible skill matching - check for partial matches and common variations
            matched_skills = 0
            for skill in required_skills:
                skill_lower = skill.lower()
                # Direct match or partial match (e.g., "scikit-learn" matches "scikit")
                if skill_lower in tech_stack_lower:
                    matched_skills += 1
                # Check for common variations
                elif skill_lower == 'scikit-learn' and ('sklearn' in tech_stack_lower or 'scikit' in tech_stack_lower):
                    matched_skills += 1
                elif skill_lower == 'tensorflow' and 'tensor' in tech_stack_lower:
                    matched_skills += 1
                elif skill_lower == 'pytorch' and 'torch' in tech_stack_lower:
                    matched_skills += 1
                elif skill_lower == 'numpy' and 'np' in tech_stack_lower:
                    matched_skills += 1
            
            # Candidate must have at least 30% of required skills (more lenient)
            threshold = max(1, len(required_skills) * 0.3)  # At least 1 skill or 30% of required
            return matched_skills >= threshold
        
        before_count = len(filtered_df)
        filtered_df = filtered_df[filtered_df['tech_stack'].apply(has_required_skills)]
        after_count = len(filtered_df)
        screening_summary.append(f"✓ Technical Skills Filter: {', '.join(required_skills[:3])}{'...' if len(required_skills) > 3 else ''} → {after_count}/{before_count} candidates passed")
    
    return filtered_df, screening_summary

def match_candidates_with_jd(client, candidates_df, job_description, top_n=5):
    """Semantic matching with TF-IDF scoring and HR-friendly language"""
    if candidates_df.empty:
        return []
    
    candidates_summary = ""
    for idx, row in candidates_df.iterrows():
        candidates_summary += f"""
Candidate {idx + 1}:
- Name: {row.get('name', 'N/A')}
- Email: {row.get('email', 'N/A')}
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

IMPORTANT: Format strengths and gaps as comma-separated points that are clear and HR-friendly.

Return JSON array:
[
  {{
    "rank": 1,
    "name": "Name",
    "email": "Email",
    "match_percentage": 88,
    "strengths": "Strong Python expertise, Extensive AWS experience, Led 5+ successful projects",
    "gaps": "Limited experience with Kubernetes, No mention of CI/CD pipelines",
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

def generate_interview_questions(client, candidate_data, job_description):
    """Generate personalized interview questions"""
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

def format_strengths_weaknesses(text):
    """Convert comma-separated text to list items."""
    if not text or text == "None" or text == "N/A":
        return []
    
    items = [item.strip() for item in text.split(',') if item.strip()]
    return items

def format_dataframe_for_display(df, columns_to_display):
    """Format dataframe with proper naming conventions."""
    from config.settings import COLUMN_DISPLAY_NAMES
    
    display_df = df[columns_to_display].copy()
    
    # Rename columns to be more readable
    display_df = display_df.rename(columns=COLUMN_DISPLAY_NAMES)
    
    return display_df