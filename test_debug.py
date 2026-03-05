import os
from dotenv import load_dotenv

load_dotenv()

print("CLIENT ID:", os.getenv("CLIENT_ID"))
print("TENANT ID:", os.getenv("TENANT_ID"))
print("SITE ID:", os.getenv("SITE_ID"))