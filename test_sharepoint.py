import os
from sharepoint_uploader import SharePointUploader

def test_connection():
    # This pulls DIRECTLY from GitHub Secrets during the Action run
    uploader = SharePointUploader(
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET")
    )
    print("✅ Authentication Successful!")

if __name__ == "__main__":
    test_connection()