"""
Resume Formatter - Extracts detailed structured data from resume text
and generates a Word document using python-docx (pure Python, no Node.js needed).
"""

import json
import io
import os
import streamlit as st
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from utils.groq_client import create_groq_completion


def extract_detailed_resume_data(client, resume_text: str, candidate_meta: dict) -> dict:
    """
    Use LLM to extract detailed structured resume data for Word doc generation.
    Falls back to existing parsed metadata for any missing fields.
    """
    fallback_client = st.session_state.get('fallback_client')

    prompt = f"""You are an expert resume parser. Extract ALL details from the resume below into structured JSON.

RULES:
- Extract exact text from the resume where possible. Do not fabricate information.
- If a section is not present in the resume, use an empty list [] or empty string "".
- For work_experience bullets, extract the actual bullet point text verbatim.

Return ONLY this JSON structure (no markdown, no extra text):
{{
  "name": "Full Name",
  "current_role": "Job Title",
  "experience_years": "X.X",
  "objective": "Full summary/objective paragraph",
  "work_experience": [
    {{
      "company": "Company Name",
      "location": "City, Country",
      "dates": "Month Year - Month Year",
      "project_title": "Project name if mentioned",
      "project_role": "Role on this project",
      "bullets": ["achievement 1", "achievement 2"],
      "technologies": "Tech1, Tech2, Tech3"
    }}
  ],
  "projects": [
    {{
      "title": "Project Title",
      "bullets": ["detail 1", "detail 2"],
      "technologies": "Tech1, Tech2"
    }}
  ],
  "skills": {{
    "Category Name": "Skill1, Skill2",
    "Another Category": "Skill3, Skill4"
  }},
  "education": "Degree, Institution, Year",
  "certifications": "Cert1, Cert2 or empty string if none",
  "email": "email or empty string",
  "phone": "phone or empty string",
  "missing_sections": ["list sections that could not be found in the resume"]
}}

Resume Text:
{resume_text[:7000]}"""

    try:
        response = create_groq_completion(
            client, fallback_client,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a precise resume parser. Return only valid JSON with no markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=3000
        )
        content = response.choices[0].message.content.strip()
        j_start = content.find('{')
        j_end   = content.rfind('}') + 1
        if j_start != -1 and j_end > j_start:
            data = json.loads(content[j_start:j_end])
            for field in ['name', 'current_role', 'email', 'phone']:
                if not data.get(field):
                    data[field] = candidate_meta.get(field, '')
            if not data.get('experience_years'):
                data['experience_years'] = str(candidate_meta.get('experience_years', ''))
            return data
    except Exception as e:
        st.warning(f"Could not fully parse resume details: {e}")

    return {
        "name":             candidate_meta.get('name', ''),
        "current_role":     candidate_meta.get('current_role', ''),
        "experience_years": str(candidate_meta.get('experience_years', '')),
        "objective":        "",
        "work_experience":  [],
        "projects":         [],
        "skills":           {},
        "education":        candidate_meta.get('education', ''),
        "certifications":   candidate_meta.get('certifications', ''),
        "email":            candidate_meta.get('email', ''),
        "phone":            candidate_meta.get('phone', ''),
        "tech_stack":       candidate_meta.get('tech_stack', ''),
        "key_projects":     candidate_meta.get('key_projects', ''),
        "missing_sections": ["Could not extract detailed information — document will use summary data only"],
    }


def check_template_completeness(data: dict) -> dict:
    warnings = list(data.get('missing_sections', []))
    if not data.get('name'):
        warnings.append("Candidate name not found")
    if not data.get('current_role'):
        warnings.append("Job title not found")
    if not data.get('experience_years'):
        warnings.append("Years of experience not specified")
    has_work = bool(data.get('work_experience') or data.get('key_projects'))
    if not has_work:
        warnings.append("Work experience details are missing — the document will have limited content")
    if not data.get('skills') and not data.get('tech_stack'):
        warnings.append("Skills section not found")
    if not data.get('education'):
        warnings.append("Education details not found")
    critical = not data.get('name') or not has_work
    return {
        'complete':          len(warnings) == 0,
        'warnings':          warnings,
        'has_critical_gaps': critical,
    }


# ── python-docx helpers ───────────────────────────────────────────────────────

def _set_font(run, name='Arial', size=11, bold=False, italic=False, color=None):
    run.font.name      = name
    run.font.size      = Pt(size)
    run.font.bold      = bold
    run.font.italic    = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def _add_paragraph(doc, text='', align=WD_ALIGN_PARAGRAPH.LEFT,
                   space_before=0, space_after=4):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if text:
        run = p.add_run(text)
        _set_font(run)
    return p


def _add_section_heading(doc, text):
    """Dark blue ALL-CAPS heading with a bottom border line."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after  = Pt(2)
    run = p.add_run(text.upper())
    _set_font(run, size=11, bold=True, color=(31, 56, 100))

    # Bottom border via XML
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'),   'single')
    bottom.set(qn('w:sz'),    '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '1F3864')
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def _add_company_line(doc, company, location=''):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after  = Pt(1)
    r1 = p.add_run(company)
    _set_font(r1, bold=True)
    if location:
        r2 = p.add_run(f'   {location}')
        _set_font(r2, color=(85, 85, 85))
    return p


def _add_date_line(doc, dates):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(1)
    run = p.add_run(dates)
    _set_font(run, italic=True, color=(46, 116, 181))
    return p


def _add_project_title(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(1)
    run = p.add_run(text)
    _set_font(run, bold=True)
    return p


def _add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(1)
    run = p.add_run(text)
    _set_font(run)
    return p


def _add_skill_line(doc, label, value):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(2)
    r1 = p.add_run(f'{label}:  ')
    _set_font(r1, bold=True)
    r2 = p.add_run(value)
    _set_font(r2)
    return p


def _add_tech_line(doc, technologies):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(4)
    r1 = p.add_run('Technologies:  ')
    _set_font(r1, bold=True)
    r2 = p.add_run(technologies)
    _set_font(r2)
    return p


# ── Main generator ────────────────────────────────────────────────────────────

def generate_resume_docx(candidate_data: dict) -> bytes | None:
    """
    Generate a Word (.docx) resume in the NexTurn template format using python-docx.
    Returns raw bytes of the .docx, or None on failure.
    """
    try:
        doc = Document()

        # ── Page margins ─────────────────────────────────────────────────────
        for section in doc.sections:
            section.top_margin    = Cm(1.9)
            section.bottom_margin = Cm(1.9)
            section.left_margin   = Cm(2.2)
            section.right_margin  = Cm(2.2)

        # ── Default style ─────────────────────────────────────────────────────
        style = doc.styles['Normal']
        style.font.name = 'Arial'
        style.font.size = Pt(11)

        name      = candidate_data.get('name', 'Candidate Name')
        role      = candidate_data.get('current_role', 'Professional')
        exp_years = candidate_data.get('experience_years', '')
        summary   = candidate_data.get('objective') or candidate_data.get('summary', '')
        work      = candidate_data.get('work_experience', [])
        projects  = candidate_data.get('projects', [])
        skills    = candidate_data.get('skills', {})
        education = candidate_data.get('education', '')
        certs     = candidate_data.get('certifications', '')

        # ── Name (centred, large, dark blue) ─────────────────────────────────
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after  = Pt(2)
        r = p_name.add_run(name.upper())
        _set_font(r, size=20, bold=True, color=(31, 56, 100))

        # ── Role (centred, grey) ──────────────────────────────────────────────
        p_role = doc.add_paragraph()
        p_role.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_role.paragraph_format.space_before = Pt(0)
        p_role.paragraph_format.space_after  = Pt(6)
        r = p_role.add_run(role.upper())
        _set_font(r, size=11, color=(68, 68, 68))

        # Divider line under header
        p_div = doc.add_paragraph()
        p_div.paragraph_format.space_before = Pt(0)
        p_div.paragraph_format.space_after  = Pt(8)
        pPr = p_div._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'),   'single')
        bottom.set(qn('w:sz'),    '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), '1F3864')
        pBdr.append(bottom)
        pPr.append(pBdr)

        # ── Summary ───────────────────────────────────────────────────────────
        if summary:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(6)
            run = p.add_run(summary)
            _set_font(run)

        # ── Work Experience ───────────────────────────────────────────────────
        exp_label = f'WORK EXPERIENCE ({exp_years}YRS)' if exp_years else 'WORK EXPERIENCE'
        _add_section_heading(doc, exp_label)

        if work:
            for entry in work:
                _add_company_line(doc, entry.get('company', ''), entry.get('location', ''))
                if entry.get('dates'):
                    _add_date_line(doc, entry['dates'])
                ptitle = ': '.join(filter(None, [entry.get('project_title'), entry.get('project_role')]))
                if ptitle:
                    _add_project_title(doc, ptitle)
                for bullet in entry.get('bullets', []):
                    _add_bullet(doc, bullet)
                if entry.get('technologies'):
                    _add_tech_line(doc, entry['technologies'])
                doc.add_paragraph().paragraph_format.space_after = Pt(2)
        else:
            # Fallback: use flat fields
            key_proj = candidate_data.get('key_projects', '')
            tech     = candidate_data.get('tech_stack', '')
            if key_proj:
                _add_company_line(doc, 'Professional Experience')
                p = doc.add_paragraph()
                run = p.add_run(str(key_proj))
                _set_font(run)
            if tech:
                _add_tech_line(doc, tech)

        # ── Standalone Projects ───────────────────────────────────────────────
        if projects:
            _add_section_heading(doc, 'PROJECTS')
            for proj in projects:
                _add_project_title(doc, proj.get('title', 'Project'))
                for bullet in proj.get('bullets', []):
                    _add_bullet(doc, bullet)
                if proj.get('technologies'):
                    _add_tech_line(doc, proj['technologies'])
                doc.add_paragraph().paragraph_format.space_after = Pt(2)

        # ── Skills ────────────────────────────────────────────────────────────
        has_skill_sects = bool(skills)
        has_basic_skills = candidate_data.get('tech_stack') and not has_skill_sects

        if has_skill_sects or has_basic_skills:
            _add_section_heading(doc, 'SKILLS')
            if has_skill_sects:
                for label, value in skills.items():
                    _add_skill_line(doc, label, value)
            else:
                _add_skill_line(doc, 'Technical Skills', candidate_data.get('tech_stack', ''))

        # ── Education ─────────────────────────────────────────────────────────
        if education:
            _add_section_heading(doc, 'ACADEMIC QUALIFICATIONS')
            _add_bullet(doc, education)

        # ── Certifications ────────────────────────────────────────────────────
        if certs and certs.strip() and certs.lower() not in ('null', 'none', ''):
            _add_section_heading(doc, 'CERTIFICATIONS')
            for cert in certs.split(','):
                t = cert.strip()
                if t:
                    _add_bullet(doc, t)

        # ── Save to bytes ─────────────────────────────────────────────────────
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        st.error(f"Could not create document: {e}")
        return None