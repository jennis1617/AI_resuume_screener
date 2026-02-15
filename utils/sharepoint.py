"""
SharePoint Integration Module
Uses Microsoft Graph API (MSAL)
Supports separate INPUT and OUTPUT folders via .env config.
"""

import streamlit as st
import io
import os
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Dependency Check ────────────────────────────────────────────────────────

SHAREPOINT_AVAILABLE = False
SHAREPOINT_ERROR = None

try:
    import msal
    SHAREPOINT_AVAILABLE = True
except ImportError as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = str(e)
except Exception as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = f"Unexpected error: {str(e)}"


# ── CONFIG LOADER (FROM ENV) ───────────────────────────────────────────────

def get_sharepoint_config() -> dict:
    """Load SharePoint config from .env"""
    return {
        "tenant_id": os.getenv("TENANT_ID"),
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "site_id": os.getenv("SITE_ID"),
        "drive_id": os.getenv("DRIVE_ID"),
        "input_folder_path": os.getenv("INPUT_FOLDER_PATH"),
        "output_folder_path": os.getenv("OUTPUT_FOLDER_PATH"),
    }


# ── SharePoint Uploader Class ──────────────────────────────────────────────

class SharePointUploader:
    """Handles Microsoft Graph API interactions for SharePoint."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self) -> str:
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret,
        )

        token_response = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" not in token_response:
            raise Exception(
                f"Auth failed: {token_response.get('error_description', 'Unknown error')}"
            )

        return token_response["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    # ── Upload File ────────────────────────────────────────────────────────

    def upload_file(
        self,
        site_id: str,
        drive_id: str,
        folder_path: str,
        file_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:

        clean_path = folder_path.strip("/")

        from urllib.parse import quote
        encoded_path = quote(f"{clean_path}/{file_name}")

        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{encoded_path}:/content"
        )

        headers = {**self._headers(), "Content-Type": content_type}
        response = requests.put(url, headers=headers, data=content)

        if response.status_code not in (200, 201):
            raise Exception(f"Upload failed [{response.status_code}]: {response.text}")

        return response.json()

    # ── Upload CSV ────────────────────────────────────────────────────────

    def upload_csv(
        self,
        site_id: str,
        drive_id: str,
        folder_path: str,
        file_name: str,
        df: pd.DataFrame,
    ) -> dict:

        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        content = buf.getvalue()

        return self.upload_file(
            site_id,
            drive_id,
            folder_path,
            file_name,
            content,
            "text/csv",
        )

    # ── List Files ────────────────────────────────────────────────────────

    def list_files(self, site_id: str, drive_id: str, folder_path: str) -> list:
        clean_path = folder_path.strip("/")

        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{clean_path}:/children"
        )

        response = requests.get(url, headers=self._headers())

        if response.status_code != 200:
            raise Exception(f"List failed [{response.status_code}]: {response.text}")

        return [i for i in response.json().get("value", []) if "file" in i]

    # ── Download File ─────────────────────────────────────────────────────

    def download_file(self, download_url: str) -> bytes:
        response = requests.get(download_url)
        response.raise_for_status()
        return response.content


# ── Helper Functions ────────────────────────────────────────────────────────

def _make_uploader(config: dict) -> SharePointUploader:
    return SharePointUploader(
        tenant_id=config["tenant_id"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
    )


def connect_to_sharepoint(config: dict):
    try:
        return _make_uploader(config)
    except Exception as e:
        st.error(f"SharePoint connection error: {str(e)}")
        return None


# ── DOWNLOAD (INPUT FOLDER) ────────────────────────────────────────────────

def download_from_sharepoint(config: dict) -> list:
    try:
        uploader = _make_uploader(config)

        items = uploader.list_files(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["input_folder_path"],  # INPUT
        )

        downloaded = []

        for item in items:
            dl_url = item.get("@microsoft.graph.downloadUrl")
            if dl_url:
                content = uploader.download_file(dl_url)
                downloaded.append(
                    {
                        "name": item.get("name"),
                        "content": content,
                        "timestamp": item.get("createdDateTime"),
                    }
                )

        return downloaded

    except Exception as e:
        st.error(f"Download error: {str(e)}")
        return []


# ── UPLOAD FILE (OUTPUT FOLDER) ────────────────────────────────────────────

def upload_to_sharepoint(config: dict, file_content: bytes, file_name: str) -> bool:
    try:
        uploader = _make_uploader(config)

        uploader.upload_file(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["output_folder_path"],  # OUTPUT
            file_name=file_name,
            content=file_content,
        )

        return True

    except Exception as e:
        st.error(f"Upload error: {str(e)}")
        return False


# ── SAVE CSV (OUTPUT FOLDER) ───────────────────────────────────────────────

def save_csv_to_sharepoint(config: dict, df: pd.DataFrame, filename: str) -> bool:
    try:
        uploader = _make_uploader(config)

        uploader.upload_csv(
            site_id=config["site_id"],
            drive_id=config["drive_id"],
            folder_path=config["output_folder_path"],  # OUTPUT
            file_name=filename,
            df=df,
        )

        return True

    except Exception as e:
        st.error(f"Error saving CSV: {str(e)}")
        return False
