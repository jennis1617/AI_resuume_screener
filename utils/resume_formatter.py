import json
import io
import os
import streamlit as st
from docx import Document
from docx.shared import RGBColor
from utils.groq_client import create_groq_completion

# Path to the template uploaded by the developer
TEMPLATE_PATH = "tempalates/sample_word_template.docx"

# --- PART 1: EXTRACTION & VALIDATION ---

def extract_detailed_resume_data(client, resume_text: str, candidate_meta: dict) -> dict:
    """
    Uses One-Shot Prompting to extract structured data for both the main
    resume body and the sidebar (education and tech stack).
    """
    fallback_client = st.session_state.get('fallback_client')

    # ONE-SHOT EXAMPLE: Demonstrates mapping for the sidebar placeholders
    one_shot_example = """
    EXAMPLE INPUT:
    "John Doe, Senior Software Engineer. 5 years exp. Experts in Python, Java, SQL, AWS, Docker. 
    Worked at TechCorp from May 2019 to Present. B.S. in Computer Science."

    EXAMPLE OUTPUT:
    {
      "name": "John Doe",
      "current_role": "Senior Software Engineer",
      "summary": "Experienced software engineer with 5 years in cloud-native applications.",
      "experience_years": "5",
      "education": "Bachelor of Science in Computer Science",
      "tech_stack": ["Python", "Java", "SQL", "AWS", "Docker", "Git", "Kubernetes", "Linux", "REST APIs", "Unit Testing"],
      "work_experience": [
        {
          "company": "TechCorp",
          "location": "San Francisco",
          "dates": "May 2019 - Present",
          "project_title": "Cloud Migration",
          "bullets": [
            "Architected transition to AWS microservices",
            "Improved deployment speed by 40% using Docker"
          ],
          "technologies": "Python, AWS, Docker"
        }
      ],
      "skills": {
        "Backend Languages": "Python, Java",
        "Containers & Orchestration": "Docker, Kubernetes",
        "Databases": "SQL, PostgreSQL",
        "Operating Systems": "Linux",
        "Version Control & Tools": "Git, AWS",
        "Testing": "Unit Testing"
      }
    }
    """

    prompt = f"""You are a precise resume parser. Extract details into JSON.
    
    IMPORTANT: Provide at least 12 distinct items in the 'tech_stack' list to fill the sidebar placeholders.
    Map the main degree into the 'education' field for the sidebar.

    {one_shot_example}

    RESUME TEXT:
    {resume_text[:7000]}
    
    RETURN ONLY VALID JSON:"""

    try:
        response = create_groq_completion(
            client, fallback_client,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return only valid JSON based on the example structure."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content[content.find('{'):content.rfind('}')+1])
    except Exception as e:
        st.warning(f"AI Extraction failed: {e}")
        return candidate_meta

def check_template_completeness(data: dict) -> dict:
    """
    REQUIRED BY UI: Checks if mandatory fields are present.
    If missing, it returns warnings to the HR dashboard.
    """
    warnings = []
    if not data.get('name'): warnings.append("Candidate Name missing")
    if not data.get('education'): warnings.append("Academic Qualifications missing")
    if not data.get('tech_stack') or len(data.get('tech_stack', [])) < 5: 
        warnings.append("Insufficient Key Skills for sidebar")
    
    return {
        'complete': len(warnings) == 0,
        'warnings': warnings,
        'has_critical_gaps': not data.get('name')
    }

# --- PART 2: WORD TEMPLATE AUTOMATION ---

def generate_resume_docx(candidate_data: dict) -> bytes | None:
    """Automates filling the Word template, including the sidebar and main body."""
    try:
        if not os.path.exists(TEMPLATE_PATH):
            st.error(f"Template not found: {TEMPLATE_PATH}")
            return None

        doc = Document(TEMPLATE_PATH)
        
        # Prepare Sidebar Skills list (populating {tech_stack} sequentially)
        sidebar_skills = candidate_data.get("tech_stack", [])
        if isinstance(sidebar_skills, str):
            sidebar_skills = [s.strip() for s in sidebar_skills.split(",")]
        
        # Prepare Main Content Data Map
        work = candidate_data.get("work_experience", [])
        p1 = work[0] if len(work) > 0 else {}
        p1_bullets = p1.get("bullets", [])
        skills_detailed = candidate_data.get("skills", {})

        data_map = {
            "NAME": candidate_data.get("name"),
            "ROLE": candidate_data.get("current_role"),
            "Professional Summary": candidate_data.get("summary"),
            "experience_years": candidate_data.get("experience_years"),
            "HIGHEST_EDUCATION": candidate_data.get("education"),
            "COMPANY_NAME": p1.get("company"),
            "LOCATION": p1.get("location"),
            "START_DATE": p1.get("dates", "").split("-")[0] if "-" in p1.get("dates", "") else p1.get("dates"),
            "END_DATE": p1.get("dates", "").split("-")[1] if "-" in p1.get("dates", "") else "",
            "PROJECT1_NAME": p1.get("project_title"),
            "TECHNOLOGIES_USED": p1.get("technologies"),
            "BACKEND_LANGUAGES": skills_detailed.get("Backend Languages"),
            "CONTAINERS_AND_ORCHESTRATION": skills_detailed.get("Containers & Orchestration"),
            "DATABASES": skills_detailed.get("Databases"),
            "OPERATING_SYSTEMS": skills_detailed.get("Operating Systems"),
            "VERSION_CONTROL_TOOLS": skills_detailed.get("Version Control & Tools"),
            "TESTING_TOOLS": skills_detailed.get("Testing"),
        }

        # Handle Project 1 numbered bullets
        for i in range(1, 7):
            data_map[f"ABOUT_PROJECT_BULLET_{i}"] = p1_bullets[i-1] if len(p1_bullets) >= i else ""

        # Scan paragraphs and all tables (sidebar is inside a table)
        all_paragraphs = list(doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_paragraphs.extend(cell.paragraphs)

        for para in all_paragraphs:
            _process_placeholders(para, data_map, sidebar_skills)

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        st.error(f"Docx Error: {e}")
        return None

def _process_placeholders(paragraph, data_map, skills_list):
    """Replaces tags. Missing info is highlighted RED."""
    # 1. Replace Standard Tags
    for key, val in data_map.items():
        tag = f"{{{key}}}"
        if tag in paragraph.text:
            _apply_text_and_color(paragraph, tag, val)

    # 2. Replace Sequential Sidebar {tech_stack} Tags
    while "{tech_stack}" in paragraph.text:
        next_val = skills_list.pop(0) if skills_list else None
        _apply_text_and_color(paragraph, "{tech_stack}", next_val)

def _apply_text_and_color(paragraph, tag, value):
    """Applies red color and bolding if information is missing."""
    for run in paragraph.runs:
        if tag in run.text:
            if not value or str(value).strip() == "":
                run.text = run.text.replace(tag, "Information Missing")
                run.font.color.rgb = RGBColor(255, 0, 0) # RED
                run.font.bold = True
            else:
                run.text = run.text.replace(tag, str(value))