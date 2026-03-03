"""
Resume preprocessing and parsing utilities
"""
import streamlit as st
import re
import json
from datetime import datetime
from utils.groq_client import create_groq_completion

def mask_pii(text):
    """Redacts PII before sending to LLM."""
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled=False, upload_date=None):
    """Parse resume with synchronized keys for the Word template."""
    fallback_client = st.session_state.get('fallback_client')

    # Contact Extraction
    email_extracted = None
    phone_extracted = None
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_matches = re.findall(email_pattern, resume_text)
    if email_matches: email_extracted = email_matches[0]

    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_matches = re.findall(phone_pattern, resume_text)
    if phone_matches:
        phone_extracted = ''.join(phone_matches[0]) if isinstance(phone_matches[0], tuple) else phone_matches[0]

    processed_text = mask_pii(resume_text) if mask_pii_enabled else resume_text

    # UPDATED TEMPLATE: Synchronized with .docx tags
    json_template = """
    {
        "NAME": "Full name",
        "ROLE": "Job title",
        "PROFESSIONAL_SUMMARY": "2-3 sentence summary",
        "PROFESSIONAL_SUMMARY": "2-3 sentence summary",  # Exact match for template
        "HIGHEST_EDUCATION": "Full degree name",
        "COLLEGE_NAME": "University name",
        "EDUCATION_DATES": "Graduation month/year",
        "tech_stack": ["Skill1", "Skill2", "Skill3"]
        "HIGHEST_EDUCATION": "Full degree name (e.g. Master of Science in Data Science)",
        "COLLEGE_NAME": "University name",
        "EDUCATION_DATES": "Graduation range (e.g. 2020 - 2022)",
        "experience_years": "Numeric years",
        "tech_stack": ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5", "Skill6", "Skill7", "Skill8"],
        "COMPANY_NAME": "Most recent company",
        "LOCATION": "City, State",
        "START_DATE": "MM/YYYY",
        "END_DATE": "MM/YYYY or Present",
        "PROJECT1_NAME": "Primary project title",
        "project1_bullets": ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5", "Bullet 6"],
        "TECHNOLOGIES_USED": "List of tools used in project",
        "BACKEND_LANGUAGES": "e.g. Python, Java",
        "CONTAINERS_AND_ORCHESTRATION": "e.g. Docker, Kubernetes",
        "DATABASES": "e.g. PostgreSQL, MongoDB",
        "OPERATING_SYSTEMS": "e.g. Linux, Windows",
        "VERSION_CONTROL_TOOLS": "e.g. Git, GitHub",
        "TESTING_TOOLS": "e.g. PyTest, Selenium"
    }"""

    prompt = (
        "You are an expert AI resume parser. Extract structured data.\n"
        "Return valid JSON with this exact structure:\n" + json_template +
        "\n\nResume:\n" + processed_text[:6000] +
        "\n\nReturn ONLY JSON."
    )

    try:
        chat_completion = create_groq_completion(
            client, fallback_client,
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
            
            # Re-insert PII if masked
            if mask_pii_enabled:
                if email_extracted: parsed_data['email'] = email_extracted
                if phone_extracted: parsed_data['phone'] = phone_extracted
            
            parsed_data['filename'] = filename
            parsed_data['submission_date'] = upload_date if upload_date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return parsed_data
    except Exception as e:
        st.error(f"Error parsing {filename}: {str(e)}")
        return None


def extract_jd_requirements(client, job_description):
    """Extract minimum experience and required skills from JD automatically."""
    fallback_client = st.session_state.get('fallback_client')

    prompt = f"""You are a deterministic job description parser.

Extract structured hiring requirements.

RULES:
- Extract only technical skills.
- Ignore soft skills and culture statements.
- If unclear → return empty or 0.
- Output JSON only.

EXAMPLE 1

Job Description:
"Junior Data Analyst required. Skills: SQL, Excel, Python."

Output:
{{
  "minimum_experience_years": 0,
  "required_technical_skills": ["SQL","Excel","Python"],
  "preferred_skills": [],
  "job_title": "Data Analyst",
  "seniority_level": "Entry"
}}

EXAMPLE 2

Job Description:
"Looking for Senior DevOps Engineer (7+ years).
Must have AWS, Kubernetes, Terraform.
Preferred: Docker, Jenkins."

Output:
{{
  "minimum_experience_years": 7,
  "required_technical_skills": ["AWS","Kubernetes","Terraform"],
  "preferred_skills": ["Docker","Jenkins"],
  "job_title": "DevOps Engineer",
  "seniority_level": "Senior"
}}

NOW PROCESS:

JOB DESCRIPTION:
{job_description}

Return ONLY:
{{
  "minimum_experience_years": 0,
  "required_technical_skills": [],
  "preferred_skills": [],
  "job_title": "",
  "seniority_level": ""
}}"""

    try:
        chat_completion = create_groq_completion(
            client,
            fallback_client,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing job descriptions. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=800
        )

        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            return json.loads(response[json_start:json_end])
        return None

    except Exception as e:
        st.error(f"Error extracting JD requirements: {str(e)}")
        return None