"""
Candidate Review & Scoring Tab — updated per mentor review:
1. AI-only scoring (no hybrid/semantic) using llama-3.3-70b-versatile
2. Candidates sorted highest score first
3. Info bubble rewritten as short bullet points
4. Button renamed to 'Run AI Screening'
5. Quality check: green/yellow only (no red)
6. Areas of knowledge removed
7. Word doc + PPT buttons per candidate card
8. Spinner shows 'Adding [name] to Candidate Pool...' on checkbox
"""

import json
import streamlit as st
import pandas as pd
from utils.resume_analysis import ResumeAnalyzer
from utils.file_handlers import extract_text_from_file
from utils.resume_formatter import (
    extract_detailed_resume_data,
    check_template_completeness,
    generate_resume_docx,
)
from utils.ppt_generator import generate_candidate_ppt


def render_analysis_tab(parsed_resumes, client):
    st.header("🎯 Candidate Review & Scoring")

    # ── Info bubble — concise bullet points ──────────────────────────────────
    st.markdown("""
    <div style="background:#F0F7FF; padding:16px 22px; border-radius:10px;
                border-left:5px solid #4A90D9; margin-bottom:24px;">
        <p style="color:#1A5276; margin:0 0 8px 0; font-size:1.05rem; font-weight:700;">
            How this works
        </p>
        <ul style="color:#2C3E50; margin:0; padding-left:18px;
                   font-size:0.95rem; line-height:1.85;">
            <li>Paste or upload the <strong>Job Description</strong> below</li>
            <li>Click <strong>Run AI Screening</strong> — AI scores every resume against the job</li>
            <li>Results appear ranked by score, <strong>highest first</strong></li>
            <li>☑️ Select candidates at your discretion for <strong>interview consideration</strong></li>
            <li>📋 AI generates a <strong>NexTurn-compatible</strong> structured profile document per candidate</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # ── Job Description Input ─────────────────────────────────────────────────
    st.subheader("📄 Step 1 — Enter the Job Details")

    jd_mode = st.radio(
        "How would you like to provide the job details?",
        ["Type or paste", "Upload a file (PDF or Word)"],
        horizontal=True,
        key="review_jd_mode"
    )

    job_desc = ""

    if jd_mode == "Upload a file (PDF or Word)":
        jd_file = st.file_uploader(
            "Upload job description", type=['pdf', 'docx'], key="review_jd_upload"
        )
        if jd_file:
            job_desc = extract_text_from_file(jd_file)
            if job_desc:
                st.success("✅ Job description loaded successfully!")
                with st.expander("Preview what was loaded"):
                    st.text(job_desc[:600] + ("…" if len(job_desc) > 600 else ""))
    else:
        job_desc = st.text_area(
            "Paste the job description here",
            height=180,
            placeholder="Paste the full job requirements here…",
            key="review_jd_paste"
        )

    if not job_desc or not job_desc.strip():
        st.info("👆 Please enter a job description above to continue.")
        return

    st.divider()

    # ── Launch button ─────────────────────────────────────────────────────────
    st.subheader("Step 2 — Run AI Screening")

    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        run_review = st.button(
            "Run AI Screening",
            type="primary",
            use_container_width=True
        )
    with col_info:
        st.markdown(
            f"<p style='color:#555; padding-top:10px;'>"
            f"AI will screen <strong>{len(parsed_resumes)}</strong> candidates "
            f"against this job description.</p>",
            unsafe_allow_html=True
        )

    if run_review:
        _run_full_analysis(parsed_resumes, client, job_desc)

    if 'selected_for_pool' not in st.session_state:
        st.session_state.selected_for_pool = set()

    if st.session_state.get('review_results'):
        _render_results(client)


def _run_full_analysis(parsed_resumes, client, job_desc):
    """Score every candidate with AI only. Sort by score descending."""
    st.session_state.review_results = []
    st.session_state.selected_for_pool = set()
    st.session_state.review_job_desc = job_desc

    analyzer = ResumeAnalyzer(client)
    res_list = parsed_resumes if isinstance(parsed_resumes, list) else [parsed_resumes]

    progress   = st.progress(0)
    status_box = st.empty()
    raw_results = []

    for idx, res_data in enumerate(res_list):
        name = res_data.get('name', f"Candidate {idx + 1}")
        status_box.markdown(
            f"<p style='color:#555;'> AI screening "
            f"<strong>{name}</strong> ({idx + 1}/{len(res_list)})…</p>",
            unsafe_allow_html=True
        )

        resume_text = st.session_state.get('resume_texts', {}).get(name, str(res_data))

        analysis = analyzer.analyze_resume(resume_text)
        for key in ['career_gaps', 'technical_anomalies', 'fake_indicators', 'domain_knowledge']:
            raw = analysis.get(key, [])
            if isinstance(raw, list):
                analysis[key] = [
                    str(item.get('description', item) if isinstance(item, dict) else item)
                    for item in raw
                ]
            else:
                analysis[key] = [str(raw)] if raw else []

        ai_score, breakdown, reason = _score_single(client, res_data, job_desc)

        raw_results.append({
            "metadata":    res_data,
            "analysis":    analysis,
            "final_score": ai_score,
            "breakdown":   breakdown,
            "reason":      reason,
        })

        progress.progress((idx + 1) / len(res_list))

    status_box.empty()
    progress.empty()

    # Sort highest first
    raw_results.sort(key=lambda x: x['final_score'], reverse=True)
    st.session_state.review_results = raw_results

    st.success(f"✅ AI screening complete — {len(res_list)} candidates ranked by match score.")


def _render_results(client):
    results  = st.session_state.review_results
    selected = st.session_state.selected_for_pool

    st.divider()

    total  = len(results)
    chosen = len(selected)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Candidates", total)
    c2.metric("Added to Pool",    chosen)
    c3.metric("Still to Review",  total - chosen)

    col_sel, col_desel, _ = st.columns([1, 1, 3])
    with col_sel:
        if st.button("✅ Select All", use_container_width=True):
            st.session_state.selected_for_pool = {
                r['metadata'].get('name', f"Candidate_{i}") for i, r in enumerate(results)
            }
            st.rerun()
    with col_desel:
        if st.button("☐ Clear All", use_container_width=True):
            st.session_state.selected_for_pool = set()
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"📋 All {total} Candidates — ranked by AI score")

    for idx, item in enumerate(results):
        meta        = item['metadata']
        analysis    = item['analysis']
        final_score = item.get('final_score', 0)
        name        = meta.get('name', f"Candidate_{idx + 1}")
        is_selected = name in selected

        selected_tag = "☑ Added to Pool" if is_selected else "☐ Not Selected"
        expander_title = f"#{idx + 1}  {name}   |   🎯 {final_score}% match   |   {selected_tag}"

        with st.expander(expander_title, expanded=(idx == 0 and not is_selected)):

            # Checkbox — with spinner message on selection
            checked = st.checkbox(
                f"Add **{name}** to the Candidate Pool",
                value=is_selected,
                key=f"chk_{idx}",
            )
            if checked and name not in st.session_state.selected_for_pool:
                with st.spinner(f"Adding {name} to Candidate Pool…"):
                    st.session_state.selected_for_pool.add(name)
                st.rerun()
            elif not checked and name in st.session_state.selected_for_pool:
                st.session_state.selected_for_pool.discard(name)
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

            _render_score_section(meta, final_score,
                                     item.get("breakdown", {}),
                                     item.get("reason", ""))
            st.markdown("<br>", unsafe_allow_html=True)
            _render_quality_section(analysis)
            st.markdown("<br>", unsafe_allow_html=True)
            _render_doc_buttons(client, name, meta, idx)

    if selected:
        st.divider()
        st.success(
            f"**{len(selected)}** candidate(s) in pool. "
            "Go to the **Candidate Pool** tab to view the shortlist."
        )


def _render_score_section(meta, final_score, breakdown=None, reason=""):
    st.markdown("#### 🎯 AI Match Score")

    if final_score >= 75:
        bg, border, fg = "#E8F5E9", "#A5D6A7", "#2E7D32"
    elif final_score >= 50:
        bg, border, fg = "#E3F2FD", "#90CAF9", "#1565C0"
    else:
        bg, border, fg = "#FFFDE7", "#FFE082", "#E65100"

    col_details, col_score = st.columns([2, 1])

    with col_details:
        for label, value in [
            ("📧 Email",        meta.get('email', 'Not provided')),
            ("📱 Phone",        meta.get('phone', 'Not provided')),
            ("💼 Experience",   f"{meta.get('experience_years', '?')} years"),
            ("🎯 Current Role", meta.get('current_role', 'Not specified')),
            ("💻 Key Skills",   str(meta.get('tech_stack', 'N/A'))[:130]),
        ]:
            st.markdown(
                f"<p style='font-size:1.05rem; margin:6px 0;'>"
                f"<strong>{label}:</strong> {value}</p>",
                unsafe_allow_html=True
            )

    with col_score:
        st.markdown(f"""
        <div style="text-align:center; background:{bg};
                    border:2px solid {border}; border-radius:14px; padding:22px 12px;">
            <div style="font-size:0.82rem; color:#666; margin-bottom:6px; font-weight:500;">
                AI Match Score
            </div>
            <div style="font-size:2.4rem; font-weight:700; color:{fg};">
                {final_score}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Score breakdown chart
    if breakdown:
        _render_score_breakdown(final_score, breakdown, reason)


def _render_score_breakdown(final_score, breakdown, reason):
    """
    Visual bar chart — each bar rendered with its own st.markdown call
    so Streamlit does not escape the HTML content.
    """
    weights = {
        "Skills Match":       "40% weight",
        "Experience Match":   "30% weight",
        "Projects Match":     "20% weight",
        "Domain & Education": "10% weight",
    }

    # ── Container header ─────────────────────────────────────────────────────
    st.markdown(
        f"""<div style="background:#F9FAFB; border:1px solid #E5E7EB;
                border-radius:12px; padding:20px 22px 6px 22px; margin-top:18px;">
            <p style="font-size:1rem; font-weight:700; color:#111827; margin:0 0 16px 0;">
                📊 Score Breakdown — why this candidate scored
                <strong>{final_score}%</strong>
            </p>
        </div>""",
        unsafe_allow_html=True
    )

    # ── One st.markdown per bar so Streamlit renders it properly ─────────────
    for dim, score in breakdown.items():
        weight_label = weights.get(dim, "")
        pct = max(0, min(100, score))
        if pct >= 70:
            bar_colour = "#4CAF50"
        elif pct >= 45:
            bar_colour = "#FF9800"
        else:
            bar_colour = "#F44336"

        st.markdown(
            f"""<div style="background:#F9FAFB; padding:0 22px 14px 22px;">
                <div style="display:flex; justify-content:space-between;
                            align-items:baseline; margin-bottom:5px;">
                    <span style="font-size:0.97rem; font-weight:600; color:#1F2937;">
                        {dim}
                    </span>
                    <span style="font-size:0.85rem; color:#6B7280;">
                        {weight_label} &nbsp;&middot;&nbsp;
                        <strong style="color:#111;">{pct}%</strong>
                    </span>
                </div>
                <div style="background:#E5E7EB; border-radius:999px;
                            height:14px; width:100%;">
                    <div style="background:{bar_colour}; width:{pct}%;
                                height:14px; border-radius:999px;">
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True
        )

    # ── Why this score reason ─────────────────────────────────────────────────
    if reason:
        st.markdown(
            f"""<div style="background:#F9FAFB; padding:0 22px 10px 22px;">
                <div style="padding:10px 14px; background:#F0F9FF;
                            border-left:4px solid #3B82F6; border-radius:6px;
                            font-size:0.93rem; color:#1E40AF;">
                    💡 <strong>Why this score?</strong> {reason}
                </div>
            </div>""",
            unsafe_allow_html=True
        )

    # ── Formula footnote + close container ───────────────────────────────────
    st.markdown(
        """<div style="background:#F9FAFB; padding:4px 22px 18px 22px;
                border-radius:0 0 12px 12px; border:1px solid #E5E7EB;
                border-top:none;">
            <p style="font-size:1rem; font-weight:600; color:#374151; margin:0;">
                Final score = Skills&times;40% + Experience&times;30%
                + Projects&times;20% + Domain&times;10%
            </p>
        </div>""",
        unsafe_allow_html=True
    )


def _render_quality_section(analysis):
    """Green / Yellow only — red removed. Areas of knowledge removed."""
    st.markdown("---")
    st.markdown("#### 📋 Resume Quality Check")

    if analysis.get('is_previous_employee'):
        st.info(f"ℹ️ **Worked at NexTurn before:** {analysis.get('nexturn_history_details', 'Yes')}")

    def green_box(label, msg):
        st.markdown(f"""
        <div style="background:#F0FFF4; border:1px solid #86EFAC; border-radius:8px;
                    padding:10px 14px; margin-bottom:8px;">
            <span style="color:#166534; font-weight:600;">✅ {label}:</span>
            <span style="color:#166534;"> {msg}</span>
        </div>""", unsafe_allow_html=True)

    def yellow_bullets(label, items):
        """Always render as bullet list — one point per line, no run-on sentences."""
        import re
        # Each item from the list may itself be a long sentence — split further
        # on ". Capital" or ", Capital" patterns to get atomic points
        atomic = []
        for raw in items:
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', str(raw).strip())
            for p in parts:
                p = p.strip().rstrip('. ')
                if p:
                    atomic.append(p)

        if not atomic:
            return

        if len(atomic) == 1:
            # Single short point — show inline
            st.markdown(
                f'''<div style="background:#FFFDE7; border:1px solid #FDD835;
                        border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                    <span style="color:#856404; font-weight:600;">⚠️ {label}:</span>
                    <span style="color:#5D4037;"> {atomic[0]}</span>
                </div>''', unsafe_allow_html=True
            )
        else:
            li_html = "".join(
                f'<li style="margin-bottom:5px; line-height:1.5;">{p}</li>'
                for p in atomic
            )
            st.markdown(
                f'''<div style="background:#FFFDE7; border:1px solid #FDD835;
                        border-radius:8px; padding:10px 14px; margin-bottom:8px;">
                    <span style="color:#856404; font-weight:600;">⚠️ {label}:</span>
                    <ul style="color:#5D4037; margin:7px 0 0 0; padding-left:20px;">
                        {li_html}
                    </ul>
                </div>''', unsafe_allow_html=True
            )

    gaps = analysis.get('career_gaps', [])
    if gaps:
        yellow_bullets("Gaps in work history", gaps)
    else:
        green_box("Work history", "No major gaps found")

    tech_issues = analysis.get('technical_anomalies', [])
    if tech_issues:
        yellow_bullets("Things to double-check", tech_issues)
    else:
        green_box("Experience details", "Everything looks consistent")

    concerns = analysis.get('fake_indicators', [])
    if concerns:
        yellow_bullets("Points that need a closer look", concerns)

    # Areas of knowledge — removed per mentor request


def _render_doc_buttons(client, name, meta, idx):
    """Word doc + PPT buttons inline in the candidate card."""
    st.markdown("#### 📄 Structure Resume in NexTurn Format")

    doc_key   = f"docx_bytes_{name}"
    ppt_key   = f"pptx_bytes_{name}"
    check_key = f"doc_check_{name}"
    det_key   = f"detailed_{name}"

    col_word, col_ppt = st.columns(2)

    with col_word:
        if st.button("📝 Create Word Document", key=f"word_{idx}", use_container_width=True):
            if not client:
                st.error("AI client not available.")
            else:
                with st.spinner(f"Building Word doc for {name}…"):
                    resume_text  = st.session_state.get('resume_texts', {}).get(name, str(meta))
                    detailed     = extract_detailed_resume_data(client, resume_text, meta)
                    completeness = check_template_completeness(detailed)
                    st.session_state[check_key] = completeness
                    st.session_state[det_key]   = detailed
                    st.session_state[doc_key]   = (
                        generate_resume_docx(detailed)
                        if not completeness['has_critical_gaps'] else None
                    )

        if check_key in st.session_state:
            comp = st.session_state[check_key]
            if comp['has_critical_gaps']:
                st.warning("⚠️ Resume is missing key details — document may be incomplete.")
            elif comp['warnings']:
                for w in comp['warnings'][:2]:
                    st.caption(f"ℹ️ {w}")

        if doc_key in st.session_state and st.session_state[doc_key]:
            safe = name.replace(' ', '_').replace('/', '_')
            st.download_button(
                "⬇️ Download Word Doc",
                data=st.session_state[doc_key],
                file_name=f"{safe}_resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key=f"dl_word_{idx}"
            )

    with col_ppt:
        if st.button("📊 Create PPT Profile", key=f"ppt_{idx}", use_container_width=True):
            if not client:
                st.error("AI client not available.")
            else:
                with st.spinner(f"Building PPT for {name}…"):
                    if det_key not in st.session_state:
                        resume_text = st.session_state.get('resume_texts', {}).get(name, str(meta))
                        st.session_state[det_key] = extract_detailed_resume_data(client, resume_text, meta)
                    detailed = st.session_state[det_key]
                    # Run completeness check for PPT warnings too
                    ppt_check = check_template_completeness(detailed)
                    st.session_state[f"ppt_check_{name}"] = ppt_check
                    st.session_state[ppt_key] = generate_candidate_ppt(detailed)

        # PPT warnings — same detail level as Word doc warnings
        if f"ppt_check_{name}" in st.session_state:
            ppt_comp = st.session_state[f"ppt_check_{name}"]
            if ppt_comp.get('has_critical_gaps'):
                st.warning(
                    "⚠️ **PPT may be incomplete** — the resume is missing critical details "
                    "(e.g. name or work experience). Some slides may be empty or sparse."
                )
            elif ppt_comp.get('warnings'):
                st.markdown(
                    "<p style='font-size:0.93rem; color:#555; margin:4px 0 2px 0;'>"
                    "ℹ️ <strong>Information gaps found in PPT:</strong></p>",
                    unsafe_allow_html=True
                )
                for w in ppt_comp['warnings']:
                    label = w.lower()
                    if 'work experience' in label or 'employment' in label:
                        icon, detail = "💼", "Work history section is missing or incomplete — experience slides may be empty."
                    elif 'project' in label:
                        icon, detail = "🚀", "No projects found — the projects slide will be skipped."
                    elif 'skill' in label:
                        icon, detail = "💻", "Skills section not detected — the skills area on slide 1 will be blank."
                    elif 'education' in label:
                        icon, detail = "🎓", "Education details missing — that section will show a placeholder."
                    elif 'certification' in label:
                        icon, detail = "🏆", "No certifications found — that section will be omitted."
                    elif 'summary' in label or 'objective' in label:
                        icon, detail = "📝", "No professional summary found — the summary section will be skipped."
                    else:
                        icon, detail = "ℹ️", w
                    st.markdown(
                        f"<div style='background:#FFF8E1; border-left:3px solid #F59E0B; "
                        f"border-radius:6px; padding:7px 12px; margin:4px 0; font-size:0.9rem; color:#78350F;'>"
                        f"{icon} {detail}</div>",
                        unsafe_allow_html=True
                    )

        if ppt_key in st.session_state and st.session_state[ppt_key]:
            safe = name.replace(' ', '_').replace('/', '_')
            st.download_button(
                "⬇️ Download PPT",
                data=st.session_state[ppt_key],
                file_name=f"{safe}_profile.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
                key=f"dl_ppt_{idx}"
            )


def _score_single(client, candidate_data: dict, job_desc: str) -> tuple:
    """
    AI-only scoring using llama-3.3-70b-versatile.
    Upgraded from 8b-instant because the AI score now carries 100% weight.
    """
    from utils.groq_client import create_groq_completion
    fallback_client = st.session_state.get('fallback_client')

    summary = (
        f"Name: {candidate_data.get('name', 'N/A')}\n"
        f"Experience: {candidate_data.get('experience_years', 'N/A')} years\n"
        f"Skills: {candidate_data.get('tech_stack', 'N/A')}\n"
        f"Current Role: {candidate_data.get('current_role', 'N/A')}\n"
        f"Education: {candidate_data.get('education', 'N/A')}\n"
        f"Projects: {str(candidate_data.get('key_projects', ''))[:400]}\n"
        f"Certifications: {candidate_data.get('certifications', 'None')}"
    )

    prompt = (
        "You are an expert technical recruiter. Score this candidate against the job description "
        "on a scale of 0–100. Be accurate and critical — do not inflate scores.\n\n"
        f"JOB DESCRIPTION:\n{job_desc[:2000]}\n\n"
        f"CANDIDATE:\n{summary}\n\n"
        "Score each dimension 0-100. Be accurate, do not inflate scores.\n"
        "Dimensions: skills_match (40%), experience_match (30%), "
        "projects_match (20%), domain_match (10%).\n"
        "Also give a one-sentence reason for the overall score.\n\n"
        'Return ONLY JSON: {"skills_match":<0-100>,"experience_match":<0-100>,'
        '"projects_match":<0-100>,"domain_match":<0-100>,"overall":<0-100>,"reason":"<sentence>"}'
    )

    try:
        resp = create_groq_completion(
            client, fallback_client,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a precise recruiter scoring assistant. Return only valid JSON."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        raw  = resp.choices[0].message.content.strip()
        j    = raw.find('{')
        data = json.loads(raw[j:raw.rfind('}') + 1])
        bd = {
            "Skills Match":       max(0, min(100, int(data.get("skills_match", 0)))),
            "Experience Match":   max(0, min(100, int(data.get("experience_match", 0)))),
            "Projects Match":     max(0, min(100, int(data.get("projects_match", 0)))),
            "Domain & Education": max(0, min(100, int(data.get("domain_match", 0)))),
        }
        overall = max(0, min(100, int(data.get("overall", 0))))
        if overall == 0:
            overall = round(bd["Skills Match"]*0.4 + bd["Experience Match"]*0.3
                            + bd["Projects Match"]*0.2 + bd["Domain & Education"]*0.1)
        return overall, bd, str(data.get("reason", ""))
    except Exception:
        return 0, {}, ""