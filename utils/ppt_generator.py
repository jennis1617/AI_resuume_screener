import io
import os
import streamlit as st
from pptx import Presentation
from pptx.dml.color import RGBColor

# Paths
TEMPLATE_PATH = "tempalates/sample_ppt_template.pptx"

def fill_placeholders(shape, data):
    """Recursively search and replace placeholders. Turns 'Information Missing' RED."""
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                for key, value in data.items():
                    placeholder = f"{{{key}}}"
                    if placeholder in run.text:
                        # Check if data is missing
                        if not value or str(value).strip() == "" or value == "Information Missing":
                            run.text = run.text.replace(placeholder, "Information Missing")
                            run.font.color.rgb = RGBColor(255, 0, 0) # RED
                            run.font.bold = True
                        else:
                            run.text = run.text.replace(placeholder, str(value))

    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                fill_placeholders(cell, data)

def map_resume_to_template(candidate_data):
    """Maps candidate data to flat keys used in PPT slides 1-5."""
    # Slide 1: Header & Skills
    flat_data = {
        "FULL_NAME": candidate_data.get("name"),
        "ROLE / CURRENT_ROLE": candidate_data.get("current_role"),
        "PROFESSIONAL_SUMMARY": candidate_data.get("summary"),
        "TECHNICAL_SKILLS": ", ".join(candidate_data.get("tech_stack", [])) if isinstance(candidate_data.get("tech_stack"), list) else candidate_data.get("tech_stack"),
        "EDUCATION_DETAILS": candidate_data.get("education"),
    }

    # Slides 2-5: Projects
    projects = candidate_data.get("work_experience", [])
    
    for i in range(1, 5):
        proj = projects[i-1] if len(projects) >= i else {}
        
        # Mapping to your specific template placeholders
        name = proj.get("project_title") or proj.get("company")
        duration = proj.get("dates")
        role = proj.get("role") or candidate_data.get("current_role")
        desc = proj.get("description")
        
        bullets = proj.get("bullets", [])
        resp = "\n".join([f"• {b}" for b in bullets]) if bullets else ""

        # Update data map (handling both Uppercase and CamelCase keys found in template)
        flat_data.update({
            f"PROJECT{i}_NAME": name,
            f"DURATION_PROJECT{i}": duration,
            f"DURATION_project{i}": duration, # Support for slide 3,4,5 casing
            f"ROLE_PROJECT{i}": role,
            f"ROLE_project{i}": role,
            f"Project{i}_Description": desc,
            f"Responsibilities_Project{i}": resp,
            f"Responsibilities_project{i}": resp,
        })

    return flat_data

def generate_candidate_ppt(candidate_data: dict) -> bytes | None:
    """Generates PPT and marks missing fields in Red."""
    try:
        if not os.path.exists(TEMPLATE_PATH):
            st.error(f"Template not found at {TEMPLATE_PATH}")
            return None

        prs = Presentation(TEMPLATE_PATH)
        data_map = map_resume_to_template(candidate_data)

        for slide in prs.slides:
            for shape in slide.shapes:
                fill_placeholders(shape, data_map)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        st.error(f"PPT Generation Error: {e}")
        return None