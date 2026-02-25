"""
PPT Generator — pure Python using python-pptx.
Matches NexTurn Prasad Chittiboina template:
  - Slide 1: Name+Role title, summary in bordered box, 2-col skills/education
  - Slides 2+: Project title, meta row, Description label, body text, responsibilities
  - Black text on white, thin black borders on content boxes
Add to requirements.txt: python-pptx
"""

import io
import streamlit as st

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt
from lxml import etree


# ── Colours — black/white only, matching template ─────────────────────────────
BLACK  = RGBColor(0x00, 0x00, 0x00)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
DARK   = RGBColor(0x1A, 0x1A, 0x1A)
BORDER = RGBColor(0x00, 0x00, 0x00)   # box borders like template

FONT = "Calibri"
W    = Inches(13.33)
H    = Inches(7.50)


# ── Primitives ────────────────────────────────────────────────────────────────

def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    return s


def _tb(slide, l, t, w, h, wrap=True):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tb.text_frame.word_wrap = wrap
    return tb.text_frame


def _bordered_box(slide, l, t, w, h):
    """Rectangle with thin black border and white fill — like template content boxes."""
    shp = slide.shapes.add_shape(1, l, t, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = WHITE
    shp.line.color.rgb = BORDER
    shp.line.width = Pt(0.75)
    return shp


def _thin_line(slide, l, t, w):
    """Thin horizontal black line — used as section dividers."""
    shp = slide.shapes.add_shape(1, l, t, w, Pt(1))
    shp.fill.solid()
    shp.fill.fore_color.rgb = BLACK
    shp.line.fill.background()
    return shp


def _run(para, text, size=11, bold=False, italic=False, color=None):
    r = para.add_run()
    r.text           = str(text)
    r.font.name      = FONT
    r.font.size      = Pt(size)
    r.font.bold      = bold
    r.font.italic    = italic
    r.font.color.rgb = color or DARK


def _para(tf, text, size=11, bold=False, italic=False,
          color=None, align=PP_ALIGN.LEFT, first=False, space_before=0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment    = align
    p.space_before = Pt(space_before)
    _run(p, text, size=size, bold=bold, italic=italic, color=color)
    return p


def _bullet_para(tf, text, size=11, first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.level        = 0
    p.space_before = Pt(1)
    pPr = p._p.get_or_add_pPr()
    bc  = etree.SubElement(pPr, qn('a:buChar'))
    bc.set('char', '•')
    _run(p, str(text), size=size, color=DARK)


def _footer(slide, num, total):
    """Page number bottom right — plain, no coloured bar."""
    tf = _tb(slide, Inches(11.5), Inches(7.1), Inches(1.6), Inches(0.3))
    _para(tf, f"{num} / {total}", size=11, color=DARK,
          align=PP_ALIGN.RIGHT, first=True)


# ── SLIDE 1 builder ───────────────────────────────────────────────────────────

def _slide1_profile(prs, d, total):
    """
    Slide 1 layout matching Prasad template:
      - Name — Role  (large bold title, top)
      - Summary paragraph in a bordered box
      - Two columns: left = Technical Skills (bordered), right = Education + Certs
    """
    s = _blank(prs)

    name    = d.get('name')         or 'Candidate'
    role    = d.get('current_role') or 'Professional'
    exp     = str(d.get('experience_years') or '')
    summary = d.get('objective') or d.get('summary') or ''
    skills  = d.get('skills') or {}
    edu     = d.get('education') or ''
    certs   = (d.get('certifications') or '').strip()

    # ── Title: "Name — Role" ──────────────────────────────────────────────────
    title_str = f"{name}– {role}"
    tf = _tb(s, Inches(0.3), Inches(0.08), Inches(12.7), Inches(0.55))
    _para(tf, title_str, size=28, bold=True, color=DARK, first=True)

    ty = Inches(0.65)

    # ── Summary in bordered box ───────────────────────────────────────────────
    if summary:
        box_h = Inches(1.5)
        _bordered_box(s, Inches(0.3), ty, Inches(12.7), box_h)
        tf = _tb(s, Inches(0.4), ty + Inches(0.08), Inches(12.5), box_h - Inches(0.16))
        _para(tf, summary, size=13, color=DARK, first=True)
        ty += box_h + Inches(0.15)

    # ── Section labels row ────────────────────────────────────────────────────
    col1_x, col1_w = Inches(0.3),  Inches(6.3)
    col2_x, col2_w = Inches(7.0),  Inches(6.0)

    # "Technical Expertise" label — bold, left col
    tf_lbl = _tb(s, col1_x, ty, col1_w, Inches(0.3))
    _para(tf_lbl, "Technical Expertise", size=16, bold=True, color=DARK, first=True)

    # "Education" label — bold, right col
    tf_lbl2 = _tb(s, col2_x, ty, col2_w, Inches(0.3))
    _para(tf_lbl2, "Education", size=16, bold=True, color=DARK, first=True)

    ty += Inches(0.32)

    # ── Skills bordered box (left) ────────────────────────────────────────────
    avail_h = H - ty - Inches(0.4)
    skills_box_h = avail_h
    _bordered_box(s, col1_x, ty, col1_w, skills_box_h)

    tf_skills = _tb(s, col1_x + Inches(0.1), ty + Inches(0.1),
                    col1_w - Inches(0.2), skills_box_h - Inches(0.2))

    first_para = True
    if isinstance(skills, dict) and skills:
        for cat, vals in list(skills.items())[:12]:
            p = tf_skills.paragraphs[0] if first_para else tf_skills.add_paragraph()
            p.space_before = Pt(2 if not first_para else 0)
            _run(p, f"{cat}", size=13, bold=True, color=DARK)
            first_para = False

            items = [v.strip() for v in str(vals).split(',')]
            for item in items:
                if item:
                    _bullet_para(tf_skills, item, size=13)
    elif d.get('tech_stack'):
        items = [v.strip() for v in str(d['tech_stack']).split(',')]
        for item in items:
            if item:
                _bullet_para(tf_skills, item, size=13, first=first_para)
                first_para = False

    # ── Education bordered box (right) ────────────────────────────────────────
    edu_box_h = Inches(0.55)
    _bordered_box(s, col2_x, ty, col2_w, edu_box_h)
    tf_edu = _tb(s, col2_x + Inches(0.1), ty + Inches(0.08),
                 col2_w - Inches(0.2), edu_box_h - Inches(0.16))
    _para(tf_edu, edu or '—', size=13, color=DARK, first=True)

    # ── Certifications (right, below education) ───────────────────────────────
    cert_clean = certs.lower() if certs else ''
    if certs and cert_clean not in ('none', 'null', ''):
        cert_ty = ty + edu_box_h + Inches(0.12)
        tf_cert_lbl = _tb(s, col2_x, cert_ty, col2_w, Inches(0.28))
        _para(tf_cert_lbl, "Certifications", size=16, bold=True, color=DARK, first=True)
        cert_ty += Inches(0.3)

        cert_list = [c.strip() for c in certs.split(',') if c.strip()]
        cert_box_h = Inches(0.35 * len(cert_list) + 0.2)
        _bordered_box(s, col2_x, cert_ty, col2_w, cert_box_h)
        tf_cert = _tb(s, col2_x + Inches(0.1), cert_ty + Inches(0.08),
                      col2_w - Inches(0.2), cert_box_h - Inches(0.16))
        for i, cert in enumerate(cert_list):
            _bullet_para(tf_cert, cert, size=13, first=(i == 0))

    _footer(s, 1, total)
    return s


# ── Project slide builder ─────────────────────────────────────────────────────

def _slide_project(prs, job, slide_num, total):
    """
    One slide per work experience, matching Prasad template project slides:
      Project N (bold label top-left)
      Project: Name   Duration: dates   Role: title
      Description: label
      Body text paragraph
      Responsibilities: (implicit — bullet list)
    """
    s = _blank(prs)

    proj_num   = f"Project {slide_num - 1}"
    company    = job.get('company', '')
    dates      = job.get('dates', '')
    proj_role  = job.get('project_role', '')
    proj_title = job.get('project_title', '') or company
    desc_text  = job.get('description', '')
    bullets    = job.get('bullets') or []
    tech       = job.get('technologies', '')

    # "Project N" label — top left, bold
    tf = _tb(s, Inches(0.3), Inches(0.05), Inches(3), Inches(0.35))
    _para(tf, proj_num, size=16, bold=True, color=DARK, first=True)

    # Meta row: Project name | Duration | Role
    meta_parts = []
    if proj_title: meta_parts.append(f"Project: {proj_title}")
    if dates:      meta_parts.append(f"Duration : {dates}")
    if proj_role:  meta_parts.append(f"Role: {proj_role}")

    tf_meta = _tb(s, Inches(0.3), Inches(0.38), Inches(12.7), Inches(0.45))
    first_meta = True
    for part in meta_parts:
        _para(tf_meta, part, size=14, bold=False, color=DARK,
              first=first_meta, space_before=0)
        first_meta = False

    ty = Inches(1.05)

    # "Description:" label
    tf_d = _tb(s, Inches(0.3), ty, Inches(2.5), Inches(0.28))
    _para(tf_d, "Description:", size=15, bold=True, color=DARK, first=True)
    ty += Inches(0.42)

    # Description body — if no desc use a generic placeholder
    body = desc_text or f"Work experience at {company}." if company else ""
    if body:
        desc_h = Inches(2.0)
        tf_body = _tb(s, Inches(0.3), ty, Inches(12.7), desc_h)
        _para(tf_body, body, size=13, color=DARK, first=True)
        ty += desc_h + Inches(0.05)

    # Responsibilities bullets
    if bullets:
        tf_r = _tb(s, Inches(0.3), ty, Inches(12.7), H - ty - Inches(0.55))
        first_b = True
        for b in bullets:
            _bullet_para(tf_r, str(b), size=13, first=first_b)
            first_b = False

    # Technologies line at bottom
    if tech:
        tf_t = _tb(s, Inches(0.3), H - Inches(0.45), Inches(12.7), Inches(0.35))
        p = tf_t.paragraphs[0]
        _run(p, "Technologies: ", size=13, bold=True, color=DARK)
        _run(p, tech, size=13, bold=False, color=DARK)

    _footer(s, slide_num, total)
    return s


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_candidate_ppt(candidate_data: dict) -> bytes | None:
    try:
        prs             = Presentation()
        prs.slide_width  = W
        prs.slide_height = H

        work     = candidate_data.get('work_experience') or []
        projects = candidate_data.get('projects') or []
        total    = 1 + len(work) + (1 if projects else 0)

        # Slide 1 — profile overview
        _slide1_profile(prs, candidate_data, total)

        # Work experience slides
        for i, job in enumerate(work):
            _slide_project(prs, job, i + 2, total)

        # Projects slide
        if projects:
            s = _blank(prs)
            tf_h = _tb(s, Inches(0.3), Inches(0.05), Inches(4), Inches(0.35))
            _para(tf_h, "Projects", size=16, bold=True, color=DARK, first=True)

            y = Inches(0.45)
            for j, proj in enumerate(projects):
                tf_t = _tb(s, Inches(0.3), y, Inches(12.7), Inches(0.35))
                _para(tf_t, proj.get('title', f'Project {j+1}'),
                      size=15, bold=True, color=DARK, first=True)
                y += Inches(0.38)

                tf_b = _tb(s, Inches(0.3), y, Inches(12.7), Inches(0.9))
                first_b = True
                for b in (proj.get('bullets') or []):
                    _bullet_para(tf_b, str(b), size=13, first=first_b)
                    first_b = False
                y += Inches(0.95)

                if proj.get('technologies'):
                    tf_tech = _tb(s, Inches(0.3), y, Inches(12.7), Inches(0.32))
                    p = tf_tech.paragraphs[0]
                    _run(p, "Technologies: ", size=13, bold=True, color=DARK)
                    _run(p, proj['technologies'], size=13, bold=False, color=DARK)
                    y += Inches(0.38)
                y += Inches(0.15)

            _footer(s, total, total)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        st.error(f"Could not generate PPT: {e}")
        return None