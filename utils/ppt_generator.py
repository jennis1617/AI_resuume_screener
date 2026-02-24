"""
PPT Generator — pure Python using python-pptx.
Design: white background, black/dark text only, large fonts that fill slides.
Add to requirements.txt:  python-pptx
"""

import io
import streamlit as st

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree


# ── Colours: white bg, black/dark text only ───────────────────────────────────
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
BLACK   = RGBColor(0x00, 0x00, 0x00)
NEAR_BK = RGBColor(0x1A, 0x1A, 0x1A)   # headings
DARK    = RGBColor(0x22, 0x22, 0x22)   # body text
SUBTEXT = RGBColor(0x44, 0x44, 0x44)   # secondary text
DIVIDER = RGBColor(0xCC, 0xCC, 0xCC)   # thin separator lines
HDRBG   = RGBColor(0x1A, 0x1A, 0x1A)   # header bar (dark, text white)

FONT    = "Calibri"
W       = Inches(13.33)
H       = Inches(7.50)


# ── Primitive helpers ─────────────────────────────────────────────────────────

def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = WHITE
    return s


def _tb(slide, l, t, w, h):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tb.text_frame.word_wrap = True
    return tb.text_frame


def _rect(slide, l, t, w, h, fill, border=None):
    shp = slide.shapes.add_shape(1, l, t, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border:
        shp.line.color.rgb = border
        shp.line.width     = Pt(0.5)
    else:
        shp.line.fill.background()
    return shp


def _run(para, text, size=14, bold=False, italic=False, color=None):
    r = para.add_run()
    r.text           = str(text)
    r.font.name      = FONT
    r.font.size      = Pt(size)
    r.font.bold      = bold
    r.font.italic    = italic
    r.font.color.rgb = color or DARK


def _para(tf, text, size=14, bold=False, italic=False,
          color=None, align=PP_ALIGN.LEFT, first=False, space_before=0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment    = align
    p.space_before = Pt(space_before)
    _run(p, text, size=size, bold=bold, italic=italic, color=color)
    return p


def _bullet(tf, text, size=13, first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.level        = 0
    p.space_before = Pt(3)
    pPr = p._p.get_or_add_pPr()
    bc  = etree.SubElement(pPr, qn('a:buChar'))
    bc.set('char', '•')
    _run(p, text, size=size, color=DARK)


# ── Structural components ─────────────────────────────────────────────────────

def _header(slide, name_text, role_text):
    """Dark header bar: candidate name large, role below it."""
    _rect(slide, Inches(0), Inches(0), W, Inches(1.35), HDRBG)
    tf = _tb(slide, Inches(0.4), Inches(0.06), Inches(12.5), Inches(0.65))
    _para(tf, name_text, size=28, bold=True, color=WHITE, first=True)
    tf2 = _tb(slide, Inches(0.4), Inches(0.72), Inches(12.5), Inches(0.5))
    _para(tf2, role_text, size=16, italic=True, color=RGBColor(0xCC,0xCC,0xCC), first=True)


def _footer(slide, num, total):
    _rect(slide, Inches(0), Inches(7.22), W, Inches(0.28), HDRBG)
    tf = _tb(slide, Inches(0.3), Inches(7.22), Inches(5), Inches(0.28))
    _para(tf, "NexTurn Candidate Profile", size=10, color=WHITE, first=True)
    tf2 = _tb(slide, Inches(11.5), Inches(7.22), Inches(1.6), Inches(0.28))
    _para(tf2, f"{num} / {total}", size=10, color=WHITE,
          align=PP_ALIGN.RIGHT, first=True)


def _section_heading(slide, text, l, t, w):
    """Bold black section title + thin grey underline."""
    tf = _tb(slide, l, t, w, Inches(0.38))
    _para(tf, text, size=15, bold=True, color=NEAR_BK, first=True)
    _rect(slide, l, t + Inches(0.36), w, Inches(0.025), DIVIDER)


# ── Main function ─────────────────────────────────────────────────────────────

def generate_candidate_ppt(candidate_data: dict) -> bytes | None:
    """
    Build a PPT profile. Returns raw bytes or None on failure.
    White background, black/dark text, large fonts filling each slide.
    """
    try:
        prs              = Presentation()
        prs.slide_width  = W
        prs.slide_height = H

        name     = candidate_data.get('name')         or 'Candidate'
        role     = candidate_data.get('current_role') or 'Professional'
        exp      = str(candidate_data.get('experience_years') or '')
        summary  = (candidate_data.get('objective') or
                    candidate_data.get('summary')   or '')
        skills   = candidate_data.get('skills')       or {}
        edu      = candidate_data.get('education')    or ''
        certs    = (candidate_data.get('certifications') or '').strip()
        work     = candidate_data.get('work_experience') or []
        projects = candidate_data.get('projects')     or []

        total = 1 + len(work) + (1 if projects else 0)

        # ══ SLIDE 1: Profile Overview ═════════════════════════════════════════
        s = _blank(prs)
        _header(s, name, f"{role}  |  {exp} years experience" if exp else role)

        content_top = Inches(1.52)   # just below header

        # If summary — full width at top of content area
        if summary:
            _section_heading(s, "Professional Summary",
                             Inches(0.4), content_top, Inches(12.5))
            tf = _tb(s, Inches(0.4), content_top + Inches(0.45),
                     Inches(12.5), Inches(1.3))
            _para(tf, summary, size=13, color=DARK, first=True)
            content_top += Inches(1.85)

        # Two-column: Skills left, Education+Certs right
        col1_x, col1_w = Inches(0.4),  Inches(6.3)
        col2_x, col2_w = Inches(7.0),  Inches(6.0)

        # ── Left: Skills ──────────────────────────────────────────────────────
        _section_heading(s, "Technical Skills", col1_x, content_top, col1_w)
        sy = content_top + Inches(0.45)

        if isinstance(skills, dict) and skills:
            for cat, vals in list(skills.items())[:7]:
                tf = _tb(s, col1_x, sy, col1_w, Inches(0.42))
                p  = tf.paragraphs[0]
                _run(p, f"{cat}:  ", size=13, bold=True,  color=NEAR_BK)
                _run(p, str(vals),   size=13, bold=False, color=DARK)
                sy += Inches(0.44)
        elif candidate_data.get('tech_stack'):
            tf = _tb(s, col1_x, sy, col1_w, Inches(2.5))
            _para(tf, str(candidate_data['tech_stack']),
                  size=13, color=DARK, first=True)

        # ── Right: Education ──────────────────────────────────────────────────
        _section_heading(s, "Education", col2_x, content_top, col2_w)
        tf = _tb(s, col2_x, content_top + Inches(0.45), col2_w, Inches(0.6))
        _para(tf, edu or '—', size=13, color=DARK, first=True)

        # ── Right: Certifications ─────────────────────────────────────────────
        cert_clean = certs.lower() if certs else ''
        if certs and cert_clean not in ('none', 'null', ''):
            cy = content_top + Inches(1.2)
            _section_heading(s, "Certifications", col2_x, cy, col2_w)
            tf = _tb(s, col2_x, cy + Inches(0.45), col2_w, Inches(2.0))
            first = True
            for cert in certs.split(','):
                t = cert.strip()
                if t:
                    _bullet(tf, t, size=13, first=first)
                    first = False

        _footer(s, 1, total)

        # ══ SLIDES 2+: Work Experience (one per job) ═════════════════════════
        for i, job in enumerate(work):
            s = _blank(prs)
            company = job.get('company', f'Company {i+1}')
            proj_role = job.get('project_role', '')
            _header(s, company, proj_role)

            # Meta row: dates | location
            meta_parts = [job.get('dates',''), job.get('location','')]
            meta_str   = '   |   '.join(p for p in meta_parts if p)

            ty = Inches(1.52)

            if meta_str:
                tf = _tb(s, Inches(0.4), ty, Inches(12.5), Inches(0.4))
                _para(tf, meta_str, size=13, italic=True, color=SUBTEXT, first=True)
                ty += Inches(0.44)

            # Project title
            if job.get('project_title'):
                _section_heading(s, job['project_title'],
                                 Inches(0.4), ty, Inches(12.5))
                ty += Inches(0.42)

            # Responsibilities
            _section_heading(s, "Responsibilities", Inches(0.4), ty, Inches(12.5))
            ty += Inches(0.42)

            bullets = job.get('bullets') or []
            # Calculate how many bullets fit — give generous height
            avail_h = Inches(7.22) - ty - Inches(0.6)
            tf = _tb(s, Inches(0.5), ty, Inches(12.3), avail_h)
            first = True
            for b in bullets:
                _bullet(tf, str(b), size=13, first=first)
                first = False

            # Technologies footer line
            if job.get('technologies'):
                tf = _tb(s, Inches(0.4), Inches(6.78),
                         Inches(12.5), Inches(0.36))
                p  = tf.paragraphs[0]
                _run(p, "Technologies:  ", size=13, bold=True,  color=NEAR_BK)
                _run(p, job['technologies'], size=13, bold=False, color=DARK)

            _footer(s, i + 2, total)

        # ══ Projects slide ════════════════════════════════════════════════════
        if projects:
            s = _blank(prs)
            _header(s, "Projects", "")

            y = Inches(1.52)
            for j, proj in enumerate(projects):
                title = proj.get('title', f'Project {j+1}')
                _section_heading(s, title, Inches(0.4), y, Inches(12.5))
                y += Inches(0.42)

                tf = _tb(s, Inches(0.5), y, Inches(12.3), Inches(1.1))
                first = True
                for b in (proj.get('bullets') or []):
                    _bullet(tf, str(b), size=13, first=first)
                    first = False
                y += Inches(1.15)

                if proj.get('technologies'):
                    tf2 = _tb(s, Inches(0.4), y, Inches(12.5), Inches(0.36))
                    p   = tf2.paragraphs[0]
                    _run(p, "Technologies:  ", size=13, bold=True,  color=NEAR_BK)
                    _run(p, proj['technologies'], size=13, bold=False, color=DARK)
                    y += Inches(0.42)

                y += Inches(0.2)

            _footer(s, total, total)

        # ── Save ──────────────────────────────────────────────────────────────
        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        st.error(f"Could not generate PPT: {e}")
        return None