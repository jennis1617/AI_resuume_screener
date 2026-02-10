import os
from dotenv import load_dotenv
import requests

# Load .env file if present (local development)
load_dotenv()


class Settings:
    """
    Configuration loader that works both locally (.env) and in GitHub Actions (secrets).
    """

    # GROQ API key
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Looks for env var (local or GitHub secret)

    # Azure AD OAuth2 credentials
    TENANT_ID = os.getenv("AZURE_TENANT_ID")
    CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

    @classmethod
    def validate(cls):
        """Ensure all required environment variables are set"""
        required_vars = ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


# Initialize settings and validate
settings = Settings()
settings.validate()


def get_access_token():
    """
    Get an OAuth2 token from Microsoft Graph using client credentials.
    Works both locally and in CI/CD (GitHub Actions secrets).
    """
    token_url = f"https://login.microsoftonline.com/{settings.TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": settings.CLIENT_ID,
        "client_secret": settings.CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()  # Raise exception if HTTP error
    token_data = response.json()
    return token_data.get("access_token")


if __name__ == "__main__":
    try:
        token = get_access_token()
        print("Access token retrieved successfully!")
        print("Token preview:", token[:20] + "...")
    except Exception as e:
        print("Failed to get access token:", e)
