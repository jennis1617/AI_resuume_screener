print("Script started")

import os
import datetime
from docx import Document

from utils.doc_generator import generate_resume_docx
from utils.preprocessing import parse_resume_with_groq
from utils.template_mapper import map_to_template_format
from utils.groq_client import init_groq_client


# -----------------------------------
# Initialize Groq Client
# -----------------------------------
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not set in environment variables")

client = init_groq_client(api_key)


# -----------------------------------
# Extract text from DOCX
# -----------------------------------
def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])


resume_path = "templates/test_resume.docx"
resume_text = extract_text_from_docx(resume_path)


# -----------------------------------
# Parse Resume
# -----------------------------------
parsed_data = parse_resume_with_groq(
    client=client,
    resume_text=resume_text,
    filename="test_resume",
    mask_pii_enabled=False,
    upload_date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

if not parsed_data:
    raise ValueError("Parsing failed")

print("Parsed Data Received")


# -----------------------------------
# Mapping Layer
# -----------------------------------
mapped_data = map_to_template_format(parsed_data)


# -----------------------------------
# Generate DOCX
# -----------------------------------
output = generate_resume_docx(
    "templates/sample_word_template.docx",
    "real_generated_resume.docx",
    mapped_data
)

print("Document generated:", output)