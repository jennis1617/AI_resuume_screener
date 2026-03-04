"""
template_mapper.py
Maps candidate data (from Groq parsing) into a flat dict
used to populate the NexTurn PPT and Word templates.
"""


def map_to_template_format(parsed_data: dict) -> dict:
    """
    Convert parsed resume JSON to the flat key format
    expected by the template population layer.
    Handles both uppercase keys (from preprocessing) and
    lowercase keys (from extract_detailed_resume_data).
    """
    if not parsed_data:
        return {}

    def _get(*keys, default=""):
        """Try multiple key variants — uppercase, lowercase, camelCase."""
        for k in keys:
            v = parsed_data.get(k)
            if v is not None and str(v).strip() not in ("", "null", "None"):
                return str(v).strip()
        return default

    def _get_list(*keys):
        for k in keys:
            v = parsed_data.get(k)
            if isinstance(v, list) and v:
                return v
        return []

    # ── Work experience projects ───────────────────────────────────────────────
    work = parsed_data.get("work_experience") or []
    projects_map = {}
    for i in range(1, 5):
        proj = work[i - 1] if len(work) >= i else {}
        bullets = proj.get("bullets") or []
        resp = "\n".join(f"• {b}" for b in bullets) if bullets else ""
        name = proj.get("project_title") or proj.get("company") or ""
        duration = proj.get("dates") or ""
        role = (proj.get("project_role") or proj.get("role") or
                parsed_data.get("current_role") or parsed_data.get("ROLE") or "")
        desc = proj.get("description") or ""

        projects_map[f"PROJECT{i}_NAME"] = name
        projects_map[f"DURATION_PROJECT{i}"] = duration
        projects_map[f"ROLE_PROJECT{i}"] = role
        projects_map[f"Project{i}_Description"] = desc
        projects_map[f"Responsibilities_Project{i}"] = resp
        # bullet list for Word doc use
        projects_map[f"project{i}_bullets"] = bullets

    # ── Skills flat string ────────────────────────────────────────────────────
    skills = parsed_data.get("skills") or {}
    tech_stack = parsed_data.get("tech_stack") or []
    if isinstance(skills, dict) and skills:
        skills_str = "; ".join(f"{k}: {v}" for k, v in skills.items())
    elif isinstance(tech_stack, list):
        skills_str = ", ".join(tech_stack)
    else:
        skills_str = str(tech_stack)

    mapped = {
        # ── Identity ──────────────────────────────────────────────────────────
        "FULL_NAME":            _get("name", "NAME"),
        "CURRENT_ROLE":         _get("current_role", "ROLE"),
        "PROFESSIONAL_SUMMARY": _get("objective", "summary", "PROFESSIONAL_SUMMARY"),
        "EXPERIENCE_YEARS":     _get("experience_years"),

        # ── Skills & Education ────────────────────────────────────────────────
        "TECHNICAL_SKILLS":     skills_str,
        "EDUCATION_DETAILS":    _get("education", "EDUCATION_DETAILS",
                                     "HIGHEST_EDUCATION"),
        "CERTIFICATIONS":       _get("certifications"),

        # ── Company / dates (most recent role) ────────────────────────────────
        "COMPANY_NAME":  work[0].get("company", "")   if work else "",
        "LOCATION":      work[0].get("location", "")  if work else "",
        "START_DATE":    (work[0].get("dates") or "").split("–")[0].strip() if work else "",
        "END_DATE":      (work[0].get("dates") or "").split("–")[-1].strip() if work else "",

        # ── Projects 1–4 ─────────────────────────────────────────────────────
        **projects_map,
    }

    return mapped