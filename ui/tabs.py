import streamlit as st
import pandas as pd
from io import BytesIO

from utils.resume_parser import parse_resume
from utils.file_handlers import extract_text_from_file
from utils.sharepoint import (
    SHAREPOINT_AVAILABLE,
    download_from_sharepoint,
    save_csv_to_sharepoint,
    upload_file_from_tabs,
    list_jds_for_dropdown,
    download_single_jd,
)

# ---------------------------------------------------------
# Helper: Check SharePoint Connection
# ---------------------------------------------------------
def _sp_wrapped():
    return (
        SHAREPOINT_AVAILABLE and
        "sharepoint_config" in st.session_state and
        st.session_state.sharepoint_config.get("connected", False)
    )

# =========================================================
# UPLOAD TAB
# =========================================================
def render_upload_tab(client=None):

    st.subheader("📂 Upload Resumes")

    uploaded_files = st.file_uploader(
        "Upload PDF or DOCX resumes",
        type=["pdf", "docx"],
        accept_multiple_files=True
    )

    if uploaded_files and client:

        upload_to_sp = st.radio(
            "Also upload these resumes to SharePoint?",
            ["No", "Yes"],
            horizontal=True,
            key="upload_sp_option"
        )

        if st.button("🚀 Read All Resumes", type="primary"):

            parsed_data = []

            for file in uploaded_files:

                with st.spinner(f"Reading {file.name}..."):

                    parsed = parse_resume(file, client)

                    if parsed:
                        parsed_data.append(parsed)

                        if upload_to_sp == "Yes" and _sp_wrapped():
                            upload_file_from_tabs(
                                file,
                                st.session_state.sharepoint_config
                            )

            if parsed_data:
                df = pd.DataFrame(parsed_data)
                st.session_state["resume_df"] = df
                st.success("All resumes processed successfully!")
                st.dataframe(df)

                if _sp_wrapped():
                    csv_bytes = df.to_csv(index=False).encode()
                    save_csv_to_sharepoint(
                        st.session_state.sharepoint_config,
                        df,
                        filename="Parsed_Resumes.csv"
                    )
            else:
                st.error("No resumes were successfully parsed.")

    elif not client:
        st.warning("LLM Client not initialized.")


# =========================================================
# SHAREPOINT TAB
# =========================================================
def render_sharepoint_tab():

    st.subheader("☁️ Retrieve Files from SharePoint")

    if not _sp_wrapped():
        st.warning("SharePoint not connected.")
        return

    if st.button("🔄 Fetch Files from SharePoint"):

        files = download_from_sharepoint(
            st.session_state.sharepoint_config
        )

        if not files:
            st.info("No files found.")
            return

        for file in files:
            st.write(f"📄 {file['name']}")


# =========================================================
# ANALYSIS TAB (UPDATED JD RETRIEVAL LOGIC)
# =========================================================
def render_analysis_tab(client=None):

    st.subheader("🧠 Resume Analysis")

    if "resume_df" not in st.session_state:
        st.warning("Upload resumes first.")
        return

    jd_mode = st.radio(
        "How would you like to provide the job details?",
        [
            "Type or paste",
            "Upload a file (PDF or Word)",
            "Retrieve from SharePoint"
        ],
        horizontal=True,
        key="review_jd_mode"
    )

    job_desc = None

    # -------------------------------------------
    # Upload JD
    # -------------------------------------------
    if jd_mode == "Upload a file (PDF or Word)":

        jd_file = st.file_uploader(
            "Upload Job Description",
            type=["pdf", "docx"],
            key="jd_upload"
        )

        if jd_file:
            job_desc = extract_text_from_file(jd_file)

    # -------------------------------------------
    # Retrieve JD from SharePoint (NEW LOGIC)
    # -------------------------------------------
    elif jd_mode == "Retrieve from SharePoint":

        if not _sp_wrapped():
            st.warning("SharePoint not connected.")
            return

        sp_config = st.session_state.sharepoint_config

        all_jds = list_jds_for_dropdown(sp_config)

        if not all_jds:
            st.info("No JD's found in SharePoint.")
            return

        # Initialize My JDs if not exists
        if "my_jds" not in st.session_state:
            st.session_state.my_jds = []

        my_jds = st.session_state.my_jds

        # Split files
        my_files = [f for f in all_jds if f["name"] in my_jds]
        other_files = [f for f in all_jds if f["name"] not in my_jds]

        dropdown_options = []

        if my_files:
            dropdown_options.append("── My JDs ──")
            dropdown_options.extend([f["name"] for f in my_files])

        dropdown_options.append("── All JDs ──")
        dropdown_options.extend([f["name"] for f in other_files])

        selected_jd = st.selectbox(
            "Select Job Description",
            dropdown_options
        )

        if selected_jd and "──" not in selected_jd:

            selected_file = next(
                f for f in all_jds if f["name"] == selected_jd
            )

            file_bytes = download_single_jd(
                sp_config,
                selected_file["download_url"]
            )

            if file_bytes:
                job_desc = extract_text_from_file(
                    BytesIO(file_bytes)
                )

                st.success("JD loaded from SharePoint.")

                # Add to My JDs if first time selected
                if selected_jd not in my_jds:
                    st.session_state.my_jds.append(selected_jd)

    # -------------------------------------------
    # Manual JD
    # -------------------------------------------
    else:
        job_desc = st.text_area(
            "Paste Job Description here",
            height=200
        )

    # -------------------------------------------
    # Run Analysis
    # -------------------------------------------
    if st.button("🎯 Run Analysis"):

        if not job_desc:
            st.warning("Provide Job Description first.")
            return

        df = st.session_state["resume_df"]

        st.success("Analysis Completed!")
        st.dataframe(df)