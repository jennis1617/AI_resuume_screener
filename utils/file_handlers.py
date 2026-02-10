"""
File handling utilities for PDF and DOCX extraction
"""

import streamlit as st
import PyPDF2
import docx2txt
import io

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def extract_text_from_docx(docx_file):
    """Extract text from DOCX file"""
    try:
        text = docx2txt.process(docx_file)
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return ""

def extract_text_from_file(uploaded_file):
    """Extract text from PDF or DOCX only"""
    if isinstance(uploaded_file, dict):  # SharePoint file
        file_ext = uploaded_file['name'].split('.')[-1].lower()
        file_content = io.BytesIO(uploaded_file['content'])
    else:  # Regular upload
        file_ext = uploaded_file.name.split('.')[-1].lower()
        file_content = uploaded_file
    
    if file_ext == 'pdf':
        return extract_text_from_pdf(file_content)
    elif file_ext == 'docx':
        return extract_text_from_docx(file_content)
    else:
        st.warning(f"⚠️ Unsupported file format: {file_ext}. Please upload PDF or DOCX files only.")
        return ""