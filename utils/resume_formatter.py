"""
Resume Formatter — fills NexTurn Word template by direct w:t element replacement.
Copies word_template.docx and replaces text by targeting exact XML elements,
preserving all formatting, floating textboxes, margins and layout exactly.
"""

import io
import os
import json
import copy
import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from utils.openai_client import create_openai_completion


# ── Template path ─────────────────────────────────────────────────────────────
TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates", "word_template.docx"
)


# ── LLM extraction ────────────────────────────────────────────────────────────

def extract_detailed_resume_data(client, resume_text: str, candidate_meta: dict) -> dict:
    

    prompt = f"""You are an expert resume parser. Extract ALL details from the resume below into structured JSON.

RULES:
- Extract exact text from the resume. Do not fabricate.
- For bullets, extract actual bullet text verbatim (no leading dashes or bullets).
- Return ONLY this JSON (no markdown, no explanation):
{{
  "NAME": "Full Name",
  "ROLE": "Job Title",
  "PROFESSIONAL_SUMMARY": "2-3 sentence summary",
  "experience_years": "X.X",
  "COMPANY_NAME": "Most recent company",
  "LOCATION": "City, Country",
  "START_DATE": "Mon YYYY",
  "END_DATE": "Mon YYYY or Present",
  "PROJECT1_NAME": "Primary project title with role e.g. ProjectName: Role",
  "ABOUT_PROJECT_BULLET_1": "bullet text",
  "ABOUT_PROJECT_BULLET_2": "bullet text",
  "ABOUT_PROJECT_BULLET_3": "bullet text",
  "ABOUT_PROJECT_BULLET_4": "bullet text",
  "ABOUT_PROJECT_BULLET_5": "bullet text",
  "ABOUT_PROJECT_BULLET_6": "bullet text",
  "PROJECT2_NAME": "Second project title or empty string",
  "PROJECT2_BULLET_1": "bullet text",
  "PROJECT2_BULLET_2": "bullet text",
  "PROJECT2_BULLET_3": "bullet text",
  "PROJECT2_BULLET_4": "bullet text",
  "PROJECT2_BULLET_5": "bullet text",
  "TECHNOLOGIES_USED": "Comma separated tech list",
  "HIGHEST_EDUCATION": "Full degree e.g. B.E. in Computer Science Engineering",
  "COLLEGE_NAME": "University name",
  "EDUCATION_DATES": "Month YYYY – Month YYYY",
  "tech_stack": ["Skill1","Skill2","Skill3","Skill4","Skill5","Skill6","Skill7","Skill8","Skill9","Skill10","Skill11","Skill12"],
  "BACKEND_LANGUAGES": "e.g. Python, Java",
  "CONTAINERS_AND_ORCHESTRATION": "e.g. Docker, Kubernetes",
  "DATABASES": "e.g. PostgreSQL, MongoDB",
  "OPERATING_SYSTEMS": "e.g. Linux, Windows",
  "VERSION_CONTROL_TOOLS": "e.g. Git, GitHub",
  "TESTING_TOOLS": "e.g. PyTest, Selenium"
}}

Resume:
{resume_text[:7000]}"""

    try:
        response = create_openai_completion(
            client,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise resume parser. Return only valid JSON."},
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
            if not data.get('NAME'):             data['NAME']  = candidate_meta.get('name', '')
            if not data.get('ROLE'):             data['ROLE']  = candidate_meta.get('current_role', '')
            if not data.get('experience_years'): data['experience_years'] = str(candidate_meta.get('experience_years', ''))
            return data
    except Exception as e:
        st.warning(f"Could not fully parse resume details: {e}")

    return {
        "NAME": candidate_meta.get('name', ''),
        "ROLE": candidate_meta.get('current_role', ''),
        "PROFESSIONAL_SUMMARY": candidate_meta.get('objective', ''),
        "experience_years": str(candidate_meta.get('experience_years', '')),
        "COMPANY_NAME": "", "LOCATION": "",
        "START_DATE": "", "END_DATE": "",
        "PROJECT1_NAME": "",
        **{f"ABOUT_PROJECT_BULLET_{i}": "" for i in range(1, 7)},
        "PROJECT2_NAME": "",
        **{f"PROJECT2_BULLET_{i}": "" for i in range(1, 6)},
        "TECHNOLOGIES_USED": "",
        "HIGHEST_EDUCATION": candidate_meta.get('education', ''),
        "COLLEGE_NAME": "", "EDUCATION_DATES": "",
        "tech_stack": candidate_meta.get('tech_stack', []),
        "BACKEND_LANGUAGES": "", "CONTAINERS_AND_ORCHESTRATION": "",
        "DATABASES": "", "OPERATING_SYSTEMS": "",
        "VERSION_CONTROL_TOOLS": "", "TESTING_TOOLS": "",
    }


def check_template_completeness(data: dict) -> dict:
    warnings = []
    if not data.get('NAME'):               warnings.append("Candidate name not found")
    if not data.get('ROLE'):               warnings.append("Job title not found")
    if not data.get('experience_years'):   warnings.append("Years of experience not specified")
    if not data.get('COMPANY_NAME'):       warnings.append("Company name missing")
    if not data.get('PROJECT1_NAME'):      warnings.append("Primary project not found")
    if not data.get('PROFESSIONAL_SUMMARY'): warnings.append("Professional summary missing")
    if not data.get('HIGHEST_EDUCATION'):  warnings.append("Education details not found")
    critical = not data.get('NAME') or not data.get('COMPANY_NAME')
    return {'complete': len(warnings) == 0, 'warnings': warnings, 'has_critical_gaps': critical}


# ── Paragraph helpers ─────────────────────────────────────────────────────────

def _clear_and_set_para(para, new_text, bold=None):
    """
    Replace text runs in para with new_text, preserving drawing/anchor elements.
    Drawings (floating textboxes) live inside w:r elements with w:drawing children
    and must NOT be removed.
    """
    p_elem = para._p
    runs = p_elem.findall(qn('w:r'))
    if not runs:
        para.add_run(new_text)
        return

    # Separate text runs from drawing runs.
    # Drawings can be direct w:drawing children OR wrapped in mc:AlternateContent.
    MC_NS = 'http://schemas.openxmlformats.org/markup-compatibility/2006'

    def _is_drawing_run(r):
        if r.find(qn('w:drawing')) is not None: return True
        if r.find(qn('w:pict'))    is not None: return True
        if r.find(f'{{{MC_NS}}}AlternateContent') is not None: return True
        return False

    text_runs    = [r for r in runs if not _is_drawing_run(r)]
    drawing_runs = [r for r in runs if     _is_drawing_run(r)]

    # Capture formatting from first text run (or first run if none)
    ref_run = text_runs[0] if text_runs else runs[0]
    rpr = ref_run.find(qn('w:rPr'))
    rpr_copy = copy.deepcopy(rpr) if rpr is not None else None

    if bold is not None and rpr_copy is not None:
        b_elem = rpr_copy.find(qn('w:b'))
        if bold and b_elem is None:
            rpr_copy.insert(0, _make_elem('w:b'))
        elif not bold and b_elem is not None:
            rpr_copy.remove(b_elem)

    # Remove ONLY text runs, keep drawing runs in place
    for r in text_runs:
        p_elem.remove(r)

    # Build new text run and insert BEFORE first drawing run (or append if none)
    new_r = _make_elem('w:r')
    if rpr_copy is not None:
        new_r.append(rpr_copy)
    t = _make_elem('w:t')
    t.text = new_text
    if new_text and (new_text[0] == ' ' or new_text[-1] == ' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    new_r.append(t)

    if drawing_runs:
        drawing_runs[0].addprevious(new_r)
    else:
        p_elem.append(new_r)


def _make_elem(tag):
    from docx.oxml import OxmlElement
    return OxmlElement(tag)


def _set_t(t_elem, text):
    """Set text on a w:t element, preserving xml:space if needed."""
    t_elem.text = text
    if text and (text[0] == ' ' or text[-1] == ' '):
        t_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    else:
        # Remove preserve if no longer needed
        attr = '{http://www.w3.org/XML/1998/namespace}space'
        if attr in t_elem.attrib:
            del t_elem.attrib[attr]


def _get_anchor_skill_slots(body):
    """
    Return list of (w:t element, current_text) for all replaceable slots
    in the first floating anchor (sidebar with education + skills).
    Slots 0-11 = education parts, slots 12-27 = skill items.
    """
    anchors = body.findall('.//' + qn('wp:anchor'))
    if not anchors:
        return []
    anchor0 = anchors[0]
    anchor0_t = anchor0.findall('.//' + qn('w:t'))
    skip = {'ACADEMIC', 'QUALIFICATIONS', 'KEY', 'SKILLS', 'OBJECTIVE', '•', ''}
    slots = []
    for t in anchor0_t:
        txt = (t.text or '').strip()
        if txt and txt not in skip:
            slots.append(t)
    return slots


# ── Main generator ─────────────────────────────────────────────────────────────

def generate_resume_docx(data: dict) -> bytes | None:
    try:
        if not os.path.exists(TEMPLATE_PATH):
            st.error(f"Word template not found at: {TEMPLATE_PATH}")
            return None

        buf_in = io.BytesIO()
        with open(TEMPLATE_PATH, 'rb') as f:
            buf_in.write(f.read())
        buf_in.seek(0)
        doc = Document(buf_in)
        body = doc.element.body

        def v(key, fallback=''):
            val = data.get(key, fallback)
            return str(val).strip() if val else fallback

        name    = v('NAME',  'Candidate Name')
        role    = v('ROLE',  'Professional')
        exp_yrs = v('experience_years', '')
        summary = v('PROFESSIONAL_SUMMARY', '')
        company = v('COMPANY_NAME', '')
        location= v('LOCATION', '')
        start   = v('START_DATE', '')
        end     = v('END_DATE', '')
        p1_name = v('PROJECT1_NAME', '')
        p2_name = v('PROJECT2_NAME', '')
        tech    = v('TECHNOLOGIES_USED', '')
        edu_deg = v('HIGHEST_EDUCATION', '')
        edu_col = v('COLLEGE_NAME', '')
        edu_dat = v('EDUCATION_DATES', '')

        bullets1 = [v(f'ABOUT_PROJECT_BULLET_{i}') for i in range(1, 7)]
        bullets1 = [b for b in bullets1 if b]

        bullets2 = [v(f'PROJECT2_BULLET_{i}') for i in range(1, 6)]
        bullets2 = [b for b in bullets2 if b]

        tech_stack = data.get('tech_stack') or []
        if isinstance(tech_stack, str):
            tech_stack = [s.strip() for s in tech_stack.split(',') if s.strip()]
        tech_stack = [str(s) for s in tech_stack if s]

        paras = doc.paragraphs

        # ── [0] Name — set text on the actual name run (preserves bold/color/size) ──
        name_runs = [r for r in paras[0]._p.findall(qn('w:r'))
                     if r.find(qn('w:t')) is not None
                     and (r.find(qn('w:t')).text or '').strip()
                     and (r.find(qn('w:t')).text or '').strip() not in ('\t', ' ')]
        if name_runs:
            name_runs[0].find(qn('w:t')).text = name.upper()
        else:
            _clear_and_set_para(paras[0], f'\t{name.upper()}\t ')

        # ── [1] Role — combine all role text runs into first, preserving style ──
        MC_NS_R = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
        role_text_runs = [
            r for r in paras[1]._p.findall(qn('w:r'))
            if r.find(f'{{{MC_NS_R}}}AlternateContent') is None
            and r.find(qn('w:drawing')) is None
            and r.find(qn('w:t')) is not None
            and (r.find(qn('w:t')).text or '').strip() not in ('', '\t')
        ]
        if role_text_runs:
            # Put role in first text run, blank out the rest
            t0 = role_text_runs[0].find(qn('w:t'))
            t0.text = role.upper()
            t0.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            for r in role_text_runs[1:]:
                t = r.find(qn('w:t'))
                if t is not None:
                    t.text = ' '
        else:
            _clear_and_set_para(paras[1], f'\t{role.upper()}\t ')

        # ── [3] Summary ───────────────────────────────────────────────────────
        _clear_and_set_para(paras[3], summary)

        # ── [5] Work Experience heading ───────────────────────────────────────
        exp_label = f'{exp_yrs}YRS' if exp_yrs else 'N/A'
        _clear_and_set_para(paras[5], f'WORK EXPERIENCE ({exp_label}) ', bold=True)

        # ── Table: Company + Location header (grey row) ───────────────────────
        if doc.tables:
            cell = doc.tables[0].cell(0, 0)
            for tp in cell.paragraphs:
                if tp.text.strip():
                    loc_str = f': {location}' if location else ''
                    _clear_and_set_para(tp, f'{company}{loc_str}', bold=True)
                    break

        # ── [8] Date range ────────────────────────────────────────────────────
        date_str = f'{start} – {end}' if start and end else start or end or ''
        _clear_and_set_para(paras[8], f'{date_str} ')

        # ── [9] Project 1 name ────────────────────────────────────────────────
        _clear_and_set_para(paras[9], f'Project: {p1_name} ' if p1_name else 'Project: N/A ')

        # ── [10–15] Project 1 bullets ─────────────────────────────────────────
        for slot, para_idx in enumerate(range(10, 16)):
            if para_idx < len(paras):
                text = bullets1[slot] if slot < len(bullets1) else ''
                _clear_and_set_para(paras[para_idx], text)

        # ── [16] Project 2 name ───────────────────────────────────────────────
        if len(paras) > 16:
            if p2_name:
                _clear_and_set_para(paras[16], f'Projects: {p2_name}', bold=True)
            else:
                _clear_and_set_para(paras[16], '')

        # ── [17–21] Project 2 bullets ─────────────────────────────────────────
        for slot, para_idx in enumerate(range(17, 22)):
            if para_idx < len(paras):
                text = bullets2[slot] if slot < len(bullets2) else ''
                _clear_and_set_para(paras[para_idx], text)

        # ── [23] Technologies ─────────────────────────────────────────────────
        if len(paras) > 23:
            _clear_and_set_para(paras[23], f'Technologies: {tech}' if tech else '')

        # ── [26–37] SKILLS section (page 2 body paragraphs) ──────────────────
        skills_order = [
            ('BACKEND_LANGUAGES',          26, 27),
            ('CONTAINERS_AND_ORCHESTRATION', 28, 29),
            ('DATABASES',                  30, 31),
            ('OPERATING_SYSTEMS',          32, 33),
            ('VERSION_CONTROL_TOOLS',      34, 35),
            ('TESTING_TOOLS',              36, 37),
        ]
        for key, label_idx, val_idx in skills_order:
            if val_idx < len(paras):
                _clear_and_set_para(paras[val_idx], v(key) or 'N/A')

        # ── Floating anchor: Education + Key Skills (sidebar textboxes) ────────
        # The anchor contains w:t elements split by the original template.
        # We collect ALL non-bullet, non-header w:t elements by position and
        # replace them. Empty text must use a space ' ' so the element survives
        # XML serialisation — truly empty w:t nodes get stripped on save.

        slots = _get_anchor_skill_slots(body)

        # Education slots 0-11 (degree spread across fragments, college, dates)
        # Strategy: put full value in first slot of each group, space others
        edu_assignments = {
            0: edu_deg,   # degree → slot 0 (was 'B.')
            1: ' ',       # was 'E.'
            2: ' ',       # was ' in Computer '
            3: ' ',       # was 'Science '
            4: ' ',       # was 'Engineering '
            5: ' ',       # was 'at '
            6: edu_col,   # college → slot 6
            7: ' ',       # was 'Engineering & T'
            8: ' ',       # was 'echnology'
            9: edu_dat,   # dates → slot 9
            10: ' ',      # was '2017'
            11: ' ',      # was '– May 2021'
        }
        for slot_idx, text in edu_assignments.items():
            if slot_idx < len(slots):
                _set_t(slots[slot_idx], text or ' ')

        # Skills: slots 12-27 → one skill per slot (16 slots available)
        for i in range(16):
            slot_idx = 12 + i
            if slot_idx < len(slots):
                skill_text = tech_stack[i] if i < len(tech_stack) else ' '
                _set_t(slots[slot_idx], skill_text or ' ')

        # Save
        buf_out = io.BytesIO()
        doc.save(buf_out)
        buf_out.seek(0)
        return buf_out.read()

    except Exception as e:
        st.error(f"Could not create document: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None