"""
Application settings and configuration
"""

# Page Configuration
PAGE_CONFIG = {
    "page_title": "AI Resume Screening System",
    "page_icon": "🎯",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Custom CSS
CUSTOM_CSS = """
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    .strength-item {
        padding: 8px 12px;
        margin: 5px 0;
        background: #d4edda;
        border-left: 4px solid #28a745;
        border-radius: 4px;
    }
    .weakness-item {
        padding: 8px 12px;
        margin: 5px 0;
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        border-radius: 4px;
    }
    /* Better table styling */
    .dataframe {
        font-size: 14px;
    }
    .dataframe th {
        background-color: #667eea;
        color: white;
        font-weight: 600;
        padding: 12px;
        text-align: left;
    }
    .dataframe td {
        padding: 10px;
        border-bottom: 1px solid #ddd;
    }
    </style>
"""

# Job Description Templates
JD_TEMPLATES = {
    "Senior Python Developer": """Senior Python Developer - 5+ years

Required Skills:
- 5+ years of Python development experience
- FastAPI, Django, or Flask frameworks
- AWS services (Lambda, EC2, S3, RDS)
- Docker and Kubernetes
- PostgreSQL/MongoDB
- CI/CD pipelines (Jenkins, GitLab CI, GitHub Actions)

Responsibilities:
- Design and build scalable backend systems
- Lead technical architecture decisions
- Mentor junior developers
- Manage production deployments
- Code reviews and best practices""",
    
    "Data Scientist": """Data Scientist - ML/AI Focus

Required Skills:
- 3+ years in Machine Learning/AI
- Python (NumPy, Pandas, Scikit-learn)
- TensorFlow or PyTorch
- SQL and data warehousing
- Statistical analysis
- Generative AI experience (preferred)

Responsibilities:
- Build and deploy ML models
- Perform large-scale data analysis
- A/B testing and experimentation
- Collaborate with engineering teams""",
    
    "DevOps Engineer": """DevOps Engineer - Cloud Infrastructure

Required Skills:
- 4+ years DevOps experience
- AWS/Azure/GCP expertise
- Kubernetes, Docker, Terraform
- CI/CD automation
- Monitoring (Prometheus, Grafana)
- Scripting (Python, Bash)

Responsibilities:
- Manage cloud infrastructure
- Automate deployment pipelines
- Ensure system reliability
- Security and compliance"""
}

# Column Display Names
COLUMN_DISPLAY_NAMES = {
    'name': 'Candidate Name',
    'email': 'Email Address',
    'phone': 'Phone Number',
    'experience_years': 'Experience (Years)',
    'tech_stack': 'Technical Skills',
    'current_role': 'Current Role',
    'education': 'Education',
    'key_projects': 'Key Projects',
    'certifications': 'Certifications',
    'domain_expertise': 'Domain Expertise',
    'submission_date': 'Submission Date',
    'filename': 'Resume File'
}