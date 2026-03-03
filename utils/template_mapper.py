def map_to_template_format(parsed_data):
    """
    Convert Groq parsed JSON (uppercase keys)
    to docxtpl template format (lowercase keys).
    """

    if not parsed_data:
        return {}

    mapped = {
        "name": parsed_data.get("NAME", ""),
        "role": parsed_data.get("ROLE", ""),
        "professional_summary": parsed_data.get("PROFESSIONAL_SUMMARY", ""),
        "experience_years": parsed_data.get("experience_years", ""),

        "company_name": parsed_data.get("COMPANY_NAME", ""),
        "location": parsed_data.get("LOCATION", ""),
        "start_date": parsed_data.get("START_DATE", ""),
        "end_date": parsed_data.get("END_DATE", ""),

        "project1_name": parsed_data.get("PROJECT1_NAME", ""),
        "project1_bullets": parsed_data.get("project1_bullets", []),

        # If you later add project2 support
        "project2_name": parsed_data.get("PROJECT2_NAME", ""),
        "project2_bullets": parsed_data.get("project2_bullets", []),

        "technologies_used": parsed_data.get("TECHNOLOGIES_USED", ""),

        "highest_education": parsed_data.get("HIGHEST_EDUCATION", ""),
        "college_name": parsed_data.get("COLLEGE_NAME", ""),
        "education_dates": parsed_data.get("EDUCATION_DATES", ""),

        # You used tech_stack in preprocessing
        "technical_skills": parsed_data.get("tech_stack", []),

        "backend_languages": parsed_data.get("BACKEND_LANGUAGES", ""),
        "containers_and_orchestration": parsed_data.get("CONTAINERS_AND_ORCHESTRATION", ""),
        "databases": parsed_data.get("DATABASES", ""),
        "operating_systems": parsed_data.get("OPERATING_SYSTEMS", ""),
        "version_control_tools": parsed_data.get("VERSION_CONTROL_TOOLS", ""),
        "testing_tools": parsed_data.get("TESTING_TOOLS", "")
    }

    return mapped