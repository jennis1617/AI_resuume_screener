import json
import io
import os
import re
import copy
import shutil
import tempfile
import zipfile
import streamlit as st
from docx import Document
from docx.shared import RGBColor
from lxml import etree
from utils.groq_client import create_groq_completion

# Path to the template uploaded by the developer (absolute, based on project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(_PROJECT_ROOT, "tempalates", "sample_word_template.docx")

# Word-processing XML namespace
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Cache a local copy so OneDrive locks / multi-process conflicts don't block us
_CACHED_TEMPLATE: str | None = None


def _get_template_path() -> str:
    """
    Return a path to the template that is safe to open even when the
    original is locked by OneDrive or another process.  On first call
    the file is copied to the system temp directory; subsequent calls
    reuse the cached copy.
    """
    global _CACHED_TEMPLATE
    if _CACHED_TEMPLATE and os.path.exists(_CACHED_TEMPLATE):
        return _CACHED_TEMPLATE

    # Try opening the original first (fast path)
    try:
        doc = Document(TEMPLATE_PATH)
        del doc  # just testing access
        _CACHED_TEMPLATE = TEMPLATE_PATH
        return TEMPLATE_PATH
    except Exception:
        pass

    # Copy to temp dir to bypass OneDrive/process locks
    try:
        tmp_dir = os.path.join(tempfile.gettempdir(), "resume_screener_cache")
        os.makedirs(tmp_dir, exist_ok=True)
        cached = os.path.join(tmp_dir, "sample_word_template.docx")
        shutil.copy2(TEMPLATE_PATH, cached)
        _CACHED_TEMPLATE = cached
        return cached
    except Exception:
        pass

    # Last resort: return original and let the caller handle the error
    return TEMPLATE_PATH

# ──────────────────────────────────────────────────────────────────────
# PART 0 — TEMPLATE SCANNING (discovers ALL placeholders, inc. sidebar)
# ──────────────────────────────────────────────────────────────────────

def _scan_all_placeholders(template_path: str = TEMPLATE_PATH) -> list[str]:
    """
    Open the .docx as a ZIP and scan the raw XML of word/document.xml
    for every {PLACEHOLDER} tag — including those inside shapes, VML
    text-boxes, and any other structure python-docx cannot normally reach.

    Returns a sorted, deduplicated list of placeholder names (without braces).
    """
    placeholders: set[str] = set()
    # Regex that matches placeholder names including spaces and & (e.g. {Professional Summary})
    _PH_RE = re.compile(r"\{([A-Za-z0-9_ &]+)\}")

    # Resolve a safe path (handles OneDrive locks)
    safe_path = _get_template_path()

    # Strategy 1: read the raw ZIP XML (works even for shapes/text-boxes)
    try:
        with zipfile.ZipFile(safe_path, "r") as z:
            for xml_file in z.namelist():
                if xml_file.startswith("word/") and xml_file.endswith(".xml"):
                    raw = z.read(xml_file).decode("utf-8", errors="ignore")
                    placeholders.update(_PH_RE.findall(raw))
    except Exception:
        pass

    # Strategy 2: join w:t runs via python-docx (handles tags split across runs)
    try:
        doc = Document(safe_path)
        body_xml = doc.element.body
        all_t = body_xml.findall(f".//{{{_W_NS}}}t")
        full_text = "".join(t.text or "" for t in all_t)
        placeholders.update(_PH_RE.findall(full_text))
    except Exception:
        pass

    # Strategy 3: Hardcoded fallback — if file was locked and no placeholders
    # were discovered, use the known set from the template.
    if not placeholders:
        placeholders = {
            "NAME", "ROLE", "Professional Summary", "experience_years",
            "HIGHEST_EDUCATION", "tech_stack",
            "COMPANY_NAME", "LOCATION", "START_DATE", "END_DATE",
            "PROJECT1_NAME", "TECHNOLOGIES_USED",
            "ABOUT_PROJECT_BULLET_1", "ABOUT_PROJECT_BULLET_2",
            "ABOUT_PROJECT_BULLET_3", "ABOUT_PROJECT_BULLET_4",
            "ABOUT_PROJECT_BULLET_5", "ABOUT_PROJECT_BULLET_6",
            "PROJECT2_NAME",
            "PROJECT2_BULLET_1", "PROJECT2_BULLET_2",
            "PROJECT2_BULLET_3", "PROJECT2_BULLET_4",
            "PROJECT2_BULLET_5", "PROJECT2_BULLET_6",
            "BACKEND_LANGUAGES", "CONTAINERS_AND_ORCHESTRATION",
            "DATABASES", "OPERATING_SYSTEMS",
            "VERSION_CONTROL_TOOLS", "TESTING_TOOLS",
        }

    return sorted(placeholders)



# ──────────────────────────────────────────────────────────────────────
# PART 1 — AI EXTRACTION & VALIDATION
# ──────────────────────────────────────────────────────────────────────

def extract_detailed_resume_data(client, resume_text: str, candidate_meta: dict) -> dict:
    """
    Uses the AI model to extract structured data that covers EVERY
    placeholder discovered in the Word template — including sidebar,
    body, and shape-based placeholders.
    """
    fallback_client = st.session_state.get("fallback_client")

    # Discover every placeholder in the template so the AI knows what to fill
    all_placeholders = _scan_all_placeholders()

    # Build a human-readable list for the prompt
    ph_list_str = ", ".join(all_placeholders)

    # ONE-SHOT EXAMPLE
    one_shot_example = """
    EXAMPLE INPUT:
    "John Doe, Senior Software Engineer. 5 years exp. Experts in Python, Java, SQL, AWS, Docker.
    Worked at TechCorp from May 2019 to Present. B.S. in Computer Science."

    EXAMPLE OUTPUT:
    {
      "NAME": "John Doe",
      "ROLE": "Senior Software Engineer",
      "Professional_Summary": "Experienced software engineer with 5 years in cloud-native applications.",
      "experience_years": "5",
      "HIGHEST_EDUCATION": "Bachelor of Science in Computer Science",
      "tech_stack": ["Python", "Java", "SQL", "AWS", "Docker", "Git", "Kubernetes", "Linux", "REST APIs", "Unit Testing", "CI/CD", "Agile"],
      "COMPANY_NAME": "TechCorp",
      "LOCATION": "San Francisco",
      "START_DATE": "May 2019",
      "END_DATE": "Present",
      "PROJECT1_NAME": "Cloud Migration",
      "ABOUT_PROJECT_BULLET_1": "Architected transition to AWS microservices",
      "ABOUT_PROJECT_BULLET_2": "Improved deployment speed by 40% using Docker",
      "TECHNOLOGIES_USED": "Python, AWS, Docker",
      "PROJECT2_NAME": "API Gateway",
      "PROJECT2_BULLET_1": "Developed RESTful API serving 10K requests/s",
      "BACKEND_LANGUAGES": "Python, Java",
      "CONTAINERS_AND_ORCHESTRATION": "Docker, Kubernetes",
      "DATABASES": "SQL, PostgreSQL",
      "OPERATING_SYSTEMS": "Linux",
      "VERSION_CONTROL_TOOLS": "Git, GitHub",
      "TESTING_TOOLS": "Unit Testing, PyTest"
    }
    """

    prompt = f"""You are a precise resume parser. Your task is to extract structured data from
a resume and map it to EVERY placeholder in this list:

PLACEHOLDERS TO FILL: [{ph_list_str}]

RULES:
1. Return a single flat JSON object where each key is EXACTLY a placeholder name from the list above.
2. For "tech_stack", return a JSON array with at least 12 distinct technical skills/tools.
3. For bullet-point placeholders (ABOUT_PROJECT_BULLET_1..6, PROJECT2_BULLET_1..6), provide
   concise, impactful achievement statements. If the resume has fewer bullets than slots,
   leave extra keys as empty strings "".
4. For Professional_Summary (mapped to "Professional Summary" placeholder), write a 2-3 sentence
   professional summary based on the resume.
5. Map the candidate's highest degree into HIGHEST_EDUCATION.
6. If a placeholder cannot be filled from the resume, set its value to "".
7. Also include an "education" key (full education string) and a "skills" sub-object:
   {{"Backend Languages": "...", "Containers & Orchestration": "...", "Databases": "...",
     "Operating Systems": "...", "Version Control & Tools": "...", "Testing": "..."}}

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
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content[content.find("{"):content.rfind("}") + 1])

        # Normalise: ensure all expected keys exist; merge into a single dict
        # Also keep legacy keys so the rest of the app doesn't break
        data.setdefault("name", data.get("NAME", candidate_meta.get("name", "")))
        data.setdefault("current_role", data.get("ROLE", candidate_meta.get("current_role", "")))
        data.setdefault("summary", data.get("Professional_Summary", ""))
        data.setdefault("experience_years", candidate_meta.get("experience_years", ""))
        data.setdefault("education", data.get("HIGHEST_EDUCATION", ""))
        data.setdefault("tech_stack", [])

        # Build work_experience list for legacy consumers (PPT generator etc.)
        if "work_experience" not in data:
            p1 = {
                "company": data.get("COMPANY_NAME", ""),
                "location": data.get("LOCATION", ""),
                "dates": f"{data.get('START_DATE', '')}-{data.get('END_DATE', '')}",
                "project_title": data.get("PROJECT1_NAME", ""),
                "bullets": [
                    data.get(f"ABOUT_PROJECT_BULLET_{i}", "")
                    for i in range(1, 7) if data.get(f"ABOUT_PROJECT_BULLET_{i}")
                ],
                "technologies": data.get("TECHNOLOGIES_USED", ""),
            }
            p2 = {
                "company": "",
                "location": "",
                "dates": "",
                "project_title": data.get("PROJECT2_NAME", ""),
                "bullets": [
                    data.get(f"PROJECT2_BULLET_{i}", "")
                    for i in range(1, 7) if data.get(f"PROJECT2_BULLET_{i}")
                ],
                "technologies": "",
            }
            data["work_experience"] = [p1]
            if p2["project_title"]:
                data["work_experience"].append(p2)

        if "skills" not in data:
            data["skills"] = {
                "Backend Languages": data.get("BACKEND_LANGUAGES", ""),
                "Containers & Orchestration": data.get("CONTAINERS_AND_ORCHESTRATION", ""),
                "Databases": data.get("DATABASES", ""),
                "Operating Systems": data.get("OPERATING_SYSTEMS", ""),
                "Version Control & Tools": data.get("VERSION_CONTROL_TOOLS", ""),
                "Testing": data.get("TESTING_TOOLS", ""),
            }

        return data

    except Exception as e:
        st.warning(f"AI Extraction failed: {e}")
        return candidate_meta


def check_template_completeness(data: dict) -> dict:
    """
    REQUIRED BY UI: Checks if mandatory fields are present.
    If missing, it returns warnings to the HR dashboard.
    """
    warnings = []
    if not data.get("name") and not data.get("NAME"):
        warnings.append("Candidate Name missing")
    if not data.get("education") and not data.get("HIGHEST_EDUCATION"):
        warnings.append("Academic Qualifications missing")
    if not data.get("tech_stack") or len(data.get("tech_stack", [])) < 5:
        warnings.append("Insufficient Key Skills for sidebar")

    has_name = bool(data.get("name") or data.get("NAME"))
    return {
        "complete": len(warnings) == 0,
        "warnings": warnings,
        "has_critical_gaps": not has_name,
    }


# ──────────────────────────────────────────────────────────────────────
# PART 2 — WORD TEMPLATE AUTOMATION (XML-level, covers shapes/sidebar)
# ──────────────────────────────────────────────────────────────────────

def _build_data_map(candidate_data: dict) -> dict:
    """
    Build a flat {placeholder_tag: value} mapping from the AI-extracted data.
    Covers body, sidebar, and all known placeholders.
    """
    work = candidate_data.get("work_experience", [])
    p1 = work[0] if len(work) > 0 else {}
    p1_bullets = p1.get("bullets", [])
    p2 = work[1] if len(work) > 1 else {}
    p2_bullets = p2.get("bullets", [])
    skills_detailed = candidate_data.get("skills", {})

    data_map = {
        # Header
        "NAME": candidate_data.get("NAME", candidate_data.get("name", "")),
        "ROLE": candidate_data.get("ROLE", candidate_data.get("current_role", "")),
        "Professional Summary": candidate_data.get(
            "Professional_Summary", candidate_data.get("summary", "")
        ),
        # Sidebar
        "HIGHEST_EDUCATION": candidate_data.get(
            "HIGHEST_EDUCATION", candidate_data.get("education", "")
        ),
        # Work experience
        "experience_years": candidate_data.get("experience_years", ""),
        "COMPANY_NAME": candidate_data.get("COMPANY_NAME", p1.get("company", "")),
        "LOCATION": candidate_data.get("LOCATION", p1.get("location", "")),
        "START_DATE": candidate_data.get("START_DATE", ""),
        "END_DATE": candidate_data.get("END_DATE", ""),
        # Project 1
        "PROJECT1_NAME": candidate_data.get("PROJECT1_NAME", p1.get("project_title", "")),
        "TECHNOLOGIES_USED": candidate_data.get(
            "TECHNOLOGIES_USED", p1.get("technologies", "")
        ),
        # Project 2
        "PROJECT2_NAME": candidate_data.get("PROJECT2_NAME", p2.get("project_title", "")),
        # Skills section
        "BACKEND_LANGUAGES": candidate_data.get(
            "BACKEND_LANGUAGES", skills_detailed.get("Backend Languages", "")
        ),
        "CONTAINERS_AND_ORCHESTRATION": candidate_data.get(
            "CONTAINERS_AND_ORCHESTRATION",
            skills_detailed.get("Containers & Orchestration", ""),
        ),
        "DATABASES": candidate_data.get(
            "DATABASES", skills_detailed.get("Databases", "")
        ),
        "OPERATING_SYSTEMS": candidate_data.get(
            "OPERATING_SYSTEMS", skills_detailed.get("Operating Systems", "")
        ),
        "VERSION_CONTROL_TOOLS": candidate_data.get(
            "VERSION_CONTROL_TOOLS",
            skills_detailed.get("Version Control & Tools", ""),
        ),
        "TESTING_TOOLS": candidate_data.get(
            "TESTING_TOOLS", skills_detailed.get("Testing", "")
        ),
    }

    # Fallback for START_DATE / END_DATE from p1.dates
    if not data_map["START_DATE"] and p1.get("dates", ""):
        parts = p1["dates"].split("-")
        data_map["START_DATE"] = parts[0].strip()
        data_map["END_DATE"] = parts[1].strip() if len(parts) > 1 else ""

    # Dynamic bullet keys
    for i in range(1, 7):
        key = f"ABOUT_PROJECT_BULLET_{i}"
        data_map[key] = candidate_data.get(
            key, p1_bullets[i - 1] if i <= len(p1_bullets) else ""
        )
    for i in range(1, 7):
        key = f"PROJECT2_BULLET_{i}"
        data_map[key] = candidate_data.get(
            key, p2_bullets[i - 1] if i <= len(p2_bullets) else ""
        )

    return data_map


def _replace_across_runs(paragraph, tag, value):
    """
    Replace a placeholder tag that may be split across multiple Word XML runs.
    Joins all run texts, performs the replacement, puts the result in the
    first run and clears the rest (preserving the first run's formatting).
    If the value is missing, the replacement text is coloured RED and bolded.
    """
    runs = paragraph.runs
    if not runs:
        return

    full_text = "".join(r.text for r in runs)
    if tag not in full_text:
        return

    is_missing = not value or str(value).strip() == ""
    replacement = "Information Missing" if is_missing else str(value)
    new_text = full_text.replace(tag, replacement, 1)

    runs[0].text = new_text
    for r in runs[1:]:
        r.text = ""

    if is_missing:
        runs[0].font.color.rgb = RGBColor(255, 0, 0)
        runs[0].font.bold = True


def _replace_in_xml_tree(root_element, tag: str, value: str):
    """
    Walk ALL w:t elements in a given XML tree (body, shape, text box, etc.)
    and replace occurrences of {tag} with value.  This is the low-level
    engine that ensures sidebar shapes and other hard-to-reach areas are
    handled.

    Strategy:
      1. For every w:p (paragraph), join its run texts.
      2. If {tag} appears in the joined text, put the replaced result into
         the first run and clear the rest.
    """
    ns = f"{{{_W_NS}}}"
    is_missing = not value or str(value).strip() == ""
    replacement_text = "Information Missing" if is_missing else str(value)
    placeholder = "{" + tag + "}"

    for p_elem in root_element.iter(f"{ns}p"):
        runs = p_elem.findall(f"{ns}r")
        if not runs:
            continue
        full = ""
        t_elements = []
        for r in runs:
            for t in r.findall(f"{ns}t"):
                full += t.text or ""
                t_elements.append(t)
        if placeholder not in full:
            continue

        new_text = full.replace(placeholder, replacement_text, 1)
        # Put all text in first t, clear the rest
        if t_elements:
            t_elements[0].text = new_text
            # Preserve whitespace
            t_elements[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            for t in t_elements[1:]:
                t.text = ""

            # Colour RED if missing
            if is_missing and runs:
                rPr = runs[0].find(f"{ns}rPr")
                if rPr is None:
                    rPr = etree.SubElement(runs[0], f"{ns}rPr")
                    runs[0].insert(0, rPr)
                color_elem = rPr.find(f"{ns}color")
                if color_elem is None:
                    color_elem = etree.SubElement(rPr, f"{ns}color")
                color_elem.set(f"{ns}val", "FF0000")
                bold_elem = rPr.find(f"{ns}b")
                if bold_elem is None:
                    etree.SubElement(rPr, f"{ns}b")


def _replace_tech_stack_in_xml(root_element, skills_list: list):
    """
    Handle the sequential {tech_stack} sidebar placeholders.
    Each occurrence is replaced with the next skill from the list.
    Works at the XML level to reach shapes/text boxes.
    """
    ns = f"{{{_W_NS}}}"
    placeholder = "{tech_stack}"
    skill_idx = 0

    for p_elem in root_element.iter(f"{ns}p"):
        runs = p_elem.findall(f"{ns}r")
        if not runs:
            continue
        full = ""
        t_elements = []
        for r in runs:
            for t in r.findall(f"{ns}t"):
                full += t.text or ""
                t_elements.append(t)

        while placeholder in full and t_elements:
            val = skills_list[skill_idx] if skill_idx < len(skills_list) else ""
            skill_idx += 1
            is_missing = not val or str(val).strip() == ""
            replacement_text = "Information Missing" if is_missing else str(val)
            full = full.replace(placeholder, replacement_text, 1)

            t_elements[0].text = full
            t_elements[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            for t in t_elements[1:]:
                t.text = ""

            if is_missing and runs:
                rPr = runs[0].find(f"{ns}rPr")
                if rPr is None:
                    rPr = etree.SubElement(runs[0], f"{ns}rPr")
                    runs[0].insert(0, rPr)
                color_elem = rPr.find(f"{ns}color")
                if color_elem is None:
                    color_elem = etree.SubElement(rPr, f"{ns}color")
                color_elem.set(f"{ns}val", "FF0000")


def _remove_paragraph(paragraph):
    """Remove a paragraph element from the document XML tree."""
    p_element = paragraph._element
    parent = p_element.getparent()
    if parent is not None:
        parent.remove(p_element)


def _add_bullet_after(paragraph, text, style=None):
    """Insert a new bullet-point paragraph right after the given paragraph,
    copying the formatting/style of the reference paragraph."""
    ns = f"{{{_W_NS}}}"
    new_p = copy.deepcopy(paragraph._element)
    for r in new_p.findall(f"{ns}r"):
        new_p.remove(r)
    new_run = (
        copy.deepcopy(paragraph.runs[0]._element)
        if paragraph.runs
        else etree.SubElement(new_p, f"{ns}r")
    )
    for t in new_run.findall(f"{ns}t"):
        new_run.remove(t)
    t_elem = etree.SubElement(new_run, f"{ns}t")
    t_elem.text = text
    t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    new_p.append(new_run)
    paragraph._element.addnext(new_p)


def generate_resume_docx(candidate_data: dict) -> bytes | None:
    """
    Automates filling the Word template.
    Works at the XML level so that ALL placeholders — body paragraphs,
    tables, shapes, VML text-boxes (sidebar) — are correctly replaced.
    """
    try:
        if not os.path.exists(TEMPLATE_PATH):
            st.error(f"Template not found: {TEMPLATE_PATH}")
            return None

        doc = Document(_get_template_path())

        # Build flat data map from AI-extracted data
        data_map = _build_data_map(candidate_data)

        # Sidebar tech_stack skills list
        sidebar_skills = candidate_data.get("tech_stack", [])
        if isinstance(sidebar_skills, str):
            sidebar_skills = [s.strip() for s in sidebar_skills.split(",")]

        # ─── PASS 1: Replace all placeholders at the XML level ───────────
        # This reaches EVERYTHING: body, tables, shapes, text boxes, sidebar
        root = doc.element.body

        # Replace standard tags
        for key, val in data_map.items():
            _replace_in_xml_tree(root, key, val)

        # Replace sequential {tech_stack} tags in sidebar
        _replace_tech_stack_in_xml(root, list(sidebar_skills))

        # ─── PASS 1b: Also process python-docx paragraphs & tables ──────
        # (ensures formatting like RED/bold is applied via the high-level API
        #  for paragraphs that python-docx CAN reach)
        all_paragraphs = list(doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_paragraphs.extend(cell.paragraphs)

        for para in all_paragraphs:
            _process_placeholders(para, data_map, list(sidebar_skills))

        # ─── PASS 2: Remove empty bullet paragraphs & add overflow ──────
        work = candidate_data.get("work_experience", [])
        p1 = work[0] if len(work) > 0 else {}
        p1_bullets = p1.get("bullets", [])
        p2 = work[1] if len(work) > 1 else {}
        p2_bullets = p2.get("bullets", [])

        p1_bullet_keys = [f"ABOUT_PROJECT_BULLET_{i}" for i in range(1, 7)]
        p2_bullet_keys = [f"PROJECT2_BULLET_{i}" for i in range(1, 7)]

        body_paragraphs = list(doc.paragraphs)
        _handle_dynamic_bullets(body_paragraphs, p1_bullets, p1_bullet_keys, "ABOUT_PROJECT_BULLET_")
        _handle_dynamic_bullets(body_paragraphs, p2_bullets, p2_bullet_keys, "PROJECT2_BULLET_")

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()

    except Exception as e:
        st.error(f"Docx Error: {e}")
        return None


def _handle_dynamic_bullets(paragraphs, actual_bullets, bullet_keys, prefix):
    """
    1. Remove paragraphs whose text is empty (placeholder was blank).
    2. If there are MORE bullets than template slots, append extras after
       the last filled bullet paragraph.
    """
    template_slot_count = len(bullet_keys)
    last_bullet_para = None

    for para in paragraphs:
        text = para.text.strip()
        for i, key in enumerate(bullet_keys):
            if i < len(actual_bullets) and actual_bullets[i] and actual_bullets[i] in text:
                last_bullet_para = para
                break

    # Remove empty bullet paragraphs
    for para in list(paragraphs):
        txt = para.text.strip()
        if txt in ("", "•", "•\t", "• ", "Information Missing"):
            p_elem = para._element
            ns = f"{{{_W_NS}}}"
            pPr = p_elem.find(f"{ns}pPr")
            numPr = pPr.find(f"{ns}numPr") if pPr is not None else None
            if numPr is not None or txt.startswith("•"):
                _remove_paragraph(para)

    # Add overflow bullets beyond template slots
    if len(actual_bullets) > template_slot_count and last_bullet_para is not None:
        overflow = actual_bullets[template_slot_count:]
        for bullet_text in reversed(overflow):
            _add_bullet_after(last_bullet_para, bullet_text)


def _process_placeholders(paragraph, data_map, skills_list):
    """Replaces tags using the high-level API, handling tags split across runs."""
    full_text = paragraph.text

    for key, val in data_map.items():
        tag = f"{{{key}}}"
        if tag in full_text:
            _replace_across_runs(paragraph, tag, val)
            full_text = paragraph.text

    while "{tech_stack}" in paragraph.text:
        next_val = skills_list.pop(0) if skills_list else None
        _replace_across_runs(paragraph, "{tech_stack}", next_val)