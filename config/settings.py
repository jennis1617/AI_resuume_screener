"""
Application settings and configuration - UPDATED WITH LIGHT COLORS
"""

# Page Configuration
PAGE_CONFIG = {
    "page_title": "Recruitment Screening System",
    "page_icon": "🎯",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Custom CSS - UPDATED WITH LIGHT COLORS
CUSTOM_CSS = """
    <style>
    /* Button styling with light gradient */
    .stButton>button {
        background: linear-gradient(90deg, #7986CB 0%, #9FA8DA 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Add Column button - Light green */
    .stButton>button[kind="secondary"] {
        background: linear-gradient(90deg, #81C784 0%, #A5D6A7 100%);
        color: white;
    }
    
    /* Multiselect pills - Light blue/indigo instead of red */
    .stMultiSelect [data-baseweb="tag"] {
        background: linear-gradient(135deg, #90CAF9 0%, #64B5F6 100%) !important;
        color: white !important;
        border: none !important;
    }
    
    .stMultiSelect [data-baseweb="tag"] span {
        color: white !important;
    }
    
    /* Strength items - Light green background */
    .strength-item {
        padding: 8px 12px;
        margin: 5px 0;
        background: #E8F5E9;
        border-left: 4px solid #66BB6A;
        border-radius: 4px;
        font-size: 15px;
    }
    
    /* Weakness items - Light orange background */
    .weakness-item {
        padding: 8px 12px;
        margin: 5px 0;
        background: #FFF3E0;
        border-left: 4px solid #FFA726;
        border-radius: 4px;
        font-size: 15px;
    }
    
    /* Table styling with light colors */
    .dataframe {
        font-size: 16px;
    }
    .dataframe th {
        background: linear-gradient(135deg, #E8EAF6 0%, #C5CAE9 100%);
        color: #3F51B5;
        font-weight: 600;
        padding: 12px;
        text-align: left;
        font-size: 17px;
    }
    .dataframe td {
        padding: 10px;
        border-bottom: 1px solid #E0E0E0;
        font-size: 16px;
    }
    
    /* Remove any bright red or green */
    .stMetric {
        background-color: #FAFAFA;
        padding: 10px;
        border-radius: 8px;
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
    
    "Data Scientist": """Data Scientist - ML Focus

Required Skills:
- 3+ years in Machine Learning
- Python (NumPy, Pandas, Scikit-learn)
- TensorFlow or PyTorch
- SQL and data warehousing
- Statistical analysis
- R, Pandas

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