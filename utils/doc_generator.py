from docxtpl import DocxTemplate


def generate_resume_docx(template_path, output_path, context):
    """
    Render DOCX template using structured resume context.
    """
    doc = DocxTemplate(template_path)
    doc.render(context)
    doc.save(output_path)
    return output_path