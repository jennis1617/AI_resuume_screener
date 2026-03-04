"""
PPT Generator — uses the NexTurn sample_ppt_template.pptx as a base.
Clears each slide content and rewrites with candidate data,
preserving original layout, fonts and positioning.

Place sample_ppt_template.pptx in templates/ folder next to app.py.
"""

import io
import os
import copy
import streamlit as st

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Pt
from pptx.oxml.ns import qn
from lxml import etree

from utils.template_mapper import map_to_template_format

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates", "sample_ppt_template.pptx"
)

RED   = RGBColor(0xFF, 0x00, 0x00)
BLACK = RGBColor(0x00, 0x00, 0x00)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_run_text(run, text, missing=False):
    """Set run text; mark red+bold if missing."""
    run.text = text if text else "Information Missing"
    if missing or not text:
        run.font.color.rgb = RED
        run.font.bold = True


def _safe_write(para, text, missing=False):
    """Write text to first run of a paragraph safely."""
    if para.runs:
        _set_run_text(para.runs[0], text, missing)
        # clear extra runs
        for r in para.runs[1:]:
            r._r.getparent().remove(r._r)


# ── Slide 1: Profile ──────────────────────────────────────────────────────────

def _populate_slide1(slide, d):
    name    = d.get("FULL_NAME")            or ""
    role    = d.get("CURRENT_ROLE")         or ""
    summary = d.get("PROFESSIONAL_SUMMARY") or ""
    edu     = d.get("EDUCATION_DETAILS")    or ""

    # Build skill lines from tech_stack / skills
    skills_raw = d.get("TECHNICAL_SKILLS") or ""

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        sname = shape.name

        # ── Name/role header (Google Shape with candidate name) ───────────────
        if "Google Shape" in sname or "g86061" in sname:
            paras = shape.text_frame.paragraphs
            # Template has 3 paragraphs: "Prasad", "Chittiboina", "– Senior..."
            # Collapse into: name on first, role on last
            name_parts = name.split() if name else ["Candidate"]
            if len(paras) >= 3:
                _safe_write(paras[0], name_parts[0] if name_parts else name)
                _safe_write(paras[1], " ".join(name_parts[1:]) if len(name_parts) > 1 else "")
                _safe_write(paras[2], f"– {role}" if role else "")
            elif len(paras) == 2:
                _safe_write(paras[0], name)
                _safe_write(paras[1], f"– {role}" if role else "")
            elif paras:
                _safe_write(paras[0], f"{name} – {role}" if role else name)

        # ── Main content area (summary + skills content) ──────────────────────
        elif sname == "object 3":
            paras = shape.text_frame.paragraphs
            if not paras:
                continue
            # Write summary into the first paragraph
            _safe_write(paras[0], summary, missing=not summary)
            # Leave remaining paragraphs (skills) as-is from template
            # since they already show skill categories from Prasad's template

        # ── Education textbox ─────────────────────────────────────────────────
        elif "TextBox 16" in sname or sname.lower() == "textbox 16":
            paras = shape.text_frame.paragraphs
            if len(paras) >= 2:
                _safe_write(paras[0], "Education")
                _safe_write(paras[1], edu, missing=not edu)
            elif paras:
                _safe_write(paras[0], edu, missing=not edu)


# ── Slides 2–5: Project slides ────────────────────────────────────────────────

def _populate_project_slide(slide, proj_num, d):
    pname    = d.get(f"PROJECT{proj_num}_NAME")              or ""
    duration = d.get(f"DURATION_PROJECT{proj_num}")          or ""
    role     = d.get(f"ROLE_PROJECT{proj_num}")              or ""
    desc     = d.get(f"Project{proj_num}_Description")       or ""
    bullets  = d.get(f"project{proj_num}_bullets")           or []

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        sname = shape.name

        # ── "Project N" label ─────────────────────────────────────────────────
        if sname == "TextBox 13":
            paras = shape.text_frame.paragraphs
            # Template splits "Project" and "1" across two paragraphs
            if len(paras) >= 2:
                _safe_write(paras[0], "Project")
                _safe_write(paras[1], str(proj_num))
            elif paras:
                _safe_write(paras[0], f"Project {proj_num}")

        # ── Meta row: Project / Duration / Role ───────────────────────────────
        elif sname == "TextBox 6":
            paras = shape.text_frame.paragraphs
            # Template layout (6 paras): label, value, label, value, label, value
            meta_values = [
                ("Project:",    pname    or "–"),
                ("Duration :", duration or "–"),
                ("Role",       f": {role}" if role else ": –"),
            ]
            pair_idx = 0
            for i, para in enumerate(paras):
                if pair_idx < len(meta_values):
                    label, value = meta_values[pair_idx]
                    if i % 2 == 0:
                        _safe_write(para, label)
                    else:
                        _safe_write(para, value, missing=not value.strip("– :"))
                        pair_idx += 1

        # ── Description label ─────────────────────────────────────────────────
        elif sname == "TextBox 11":
            # Leave "Description:" label text as-is

            pass

        # ── Description body + Responsibilities ──────────────────────────────
        elif sname == "TextBox 10":
            paras = shape.text_frame.paragraphs
            if not paras:
                continue

            # Find "Responsibilities" paragraph index
            resp_idx = None
            for i, p in enumerate(paras):
                full_text = "".join(r.text for r in p.runs).lower()
                if "responsibilit" in full_text:
                    resp_idx = i
                    break

            # Write description into first paragraph
            _safe_write(paras[0], desc, missing=not desc)

            # Write bullets after Responsibilities label
            if resp_idx is not None:
                bullet_start = resp_idx + 1
                for i in range(bullet_start, len(paras)):
                    bi = i - bullet_start
                    if bi < len(bullets):
                        _safe_write(paras[i], bullets[bi])
                    else:
                        _safe_write(paras[i], "")
            elif bullets:
                # No explicit label — write bullets from para 1 onward
                for i, para in enumerate(paras[1:], 1):
                    bi = i - 1
                    if bi < len(bullets):
                        _safe_write(para, bullets[bi])
                    else:
                        _safe_write(para, "")


# ── Main ─────────────────────────────────────────────────────────────────────

def generate_candidate_ppt(candidate_data: dict) -> bytes | None:
    try:
        if not os.path.exists(TEMPLATE_PATH):
            st.error(
                f"PPT template not found. "
                f"Please place `sample_ppt_template.pptx` in the `templates/` folder "
                f"next to app.py. Expected path: {TEMPLATE_PATH}"
            )
            return None

        prs = Presentation(TEMPLATE_PATH)
        d   = map_to_template_format(candidate_data)

        if len(prs.slides) >= 1:
            _populate_slide1(prs.slides[0], d)

        for i in range(1, min(5, len(prs.slides))):
            _populate_project_slide(prs.slides[i], i, d)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        st.error(f"PPT Generation Error: {e}")
        return None