import os
from dotenv import load_dotenv

# load_dotenv() is only for your local machine; 
# GitHub Actions/Streamlit will ignore this and use their own environment.
load_dotenv() 

class Settings:
    # This reads directly from the OS environment
    TENANT_ID = os.getenv("AZURE_TENANT_ID")
    CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    @classmethod
    def validate(cls):
        required = ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"]
        missing = [v for v in required if not getattr(cls, v)]
        if missing:
            raise EnvironmentError(f"Missing: {', '.join(missing)}")

settings = Settings()