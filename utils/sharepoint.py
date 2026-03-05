"""
SharePoint Integration Module
Microsoft Graph API + MSAL Authentication
"""

import streamlit as st
import requests
import io
from datetime import datetime

# ------------------------------------------------
# Dependency Check
# ------------------------------------------------

SHAREPOINT_AVAILABLE = False
SHAREPOINT_ERROR = None

try:
    import msal
    SHAREPOINT_AVAILABLE = True
except ImportError as e:
    SHAREPOINT_ERROR = str(e)


# ------------------------------------------------
# SharePoint Uploader
# ------------------------------------------------

class SharePointUploader:

    def __init__(self, tenant_id, client_id, client_secret):

        authority = f"https://login.microsoftonline.com/{tenant_id}"

        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret
        )

        token_response = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" not in token_response:
            raise Exception("Authentication failed")

        self.access_token = token_response["access_token"]

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}"
        }

    # ------------------------------------------------
    # Upload File
    # ------------------------------------------------

    def upload_file(self, site_id, drive_id, folder_path, file_name, content):

        clean_path = folder_path.strip("/")

        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{clean_path}/{file_name}:/content"
        )

        headers = {
            **self._headers(),
            "Content-Type": "application/octet-stream"
        }

        response = requests.put(url, headers=headers, data=content)

        if response.status_code not in (200, 201):
            raise Exception(response.text)

        return response.json()

    # ------------------------------------------------
    # List Files
    # ------------------------------------------------

    def list_files(self, site_id, drive_id, folder_path):

        clean_path = folder_path.strip("/")

        url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/drives/{drive_id}/root:/{clean_path}:/children"
        )

        all_items = []

        while url:

            response = requests.get(url, headers=self._headers())

            if response.status_code != 200:
                raise Exception(response.text)

            data = response.json()

            all_items.extend(data.get("value", []))

            url = data.get("@odata.nextLink")

        files = [f for f in all_items if "file" in f]

        # remove duplicates
        seen = set()
        unique = []

        for f in files:
            name = f.get("name", "").lower()

            if name not in seen:
                seen.add(name)
                unique.append(f)

        return unique

    # ------------------------------------------------
    # Download File
    # ------------------------------------------------

    def download_file(self, download_url):

        response = requests.get(download_url)
        response.raise_for_status()

        return response.content


# ------------------------------------------------
# Helper
# ------------------------------------------------

def _make_uploader(config):

    return SharePointUploader(
        config["tenant_id"],
        config["client_id"],
        config["client_secret"]
    )


# ------------------------------------------------
# Upload JD
# ------------------------------------------------

def upload_jd_to_sharepoint(config, uploaded_file, uploaded_by):

    try:

        uploader = _make_uploader(config)

        # embed uploader name in file
        content = uploaded_file.getvalue()

        filename = uploaded_file.name

        uploader.upload_file(
            config["site_id"],
            config["drive_id"],
            config["jd_folder_path"],
            filename,
            content
        )

        return True

    except Exception as e:

        st.error(f"Upload failed: {e}")
        return False


# ------------------------------------------------
# List JDs
# ------------------------------------------------

def list_jds_from_sharepoint(config):

    try:

        uploader = _make_uploader(config)

        items = uploader.list_files(
            config["site_id"],
            config["drive_id"],
            config["jd_folder_path"]
        )

        jds = []

        for item in items:

            name = item.get("name", "")

            if not name.lower().endswith((".pdf", ".docx", ".txt")):
                continue

            created_by = (
                item.get("createdBy", {})
                .get("user", {})
                .get("displayName", "Unknown")
            )

            jds.append({
                "name": name,
                "item_id": item.get("id"),
                "uploaded_by": created_by,
                "download_url": item.get("@microsoft.graph.downloadUrl")
            })

        return jds

    except Exception as e:

        st.error(f"Could not list JDs: {e}")
        return []


# ------------------------------------------------
# Split JDs by User
# ------------------------------------------------

def split_jds_by_user(config, current_user):

    jds = list_jds_from_sharepoint(config)

    my_jds = []
    other_jds = []

    for jd in jds:

        uploader = jd["uploaded_by"].replace(".", " ").lower()
        user = current_user.replace(".", " ").lower()

        if uploader == user:
            my_jds.append(jd)
        else:
            other_jds.append(jd)

    return {
        "my_jds": my_jds,
        "other_jds": other_jds
    }


# ------------------------------------------------
# Download JD
# ------------------------------------------------

def download_jd_from_sharepoint(download_url):

    try:

        response = requests.get(download_url)
        response.raise_for_status()

        return response.content

    except Exception as e:

        st.error(f"Download error: {e}")
        return None


# ------------------------------------------------
# Delete JD
# ------------------------------------------------

def delete_jd_from_sharepoint(config, item_id):

    try:

        uploader = _make_uploader(config)

        url = (
            f"https://graph.microsoft.com/v1.0/sites/{config['site_id']}"
            f"/drives/{config['drive_id']}/items/{item_id}"
        )

        response = requests.delete(url, headers=uploader._headers())

        if response.status_code == 204:
            return True

        raise Exception(response.text)

    except Exception as e:

        st.error(f"Delete failed: {e}")
        return False


# ------------------------------------------------
# Download resumes
# ------------------------------------------------

def download_from_sharepoint(config):

    try:

        uploader = _make_uploader(config)

        items = uploader.list_files(
            config["site_id"],
            config["drive_id"],
            config["input_folder_path"]
        )

        downloaded = []

        for item in items:

            name = item.get("name", "")

            if not name.lower().endswith((".pdf", ".docx")):
                continue

            url = item.get("@microsoft.graph.downloadUrl")

            content = uploader.download_file(url)

            downloaded.append({
                "name": name,
                "content": content,
                "timestamp": item.get("createdDateTime", datetime.now().isoformat())
            })

        return downloaded

    except Exception as e:

        st.error(f"Download error: {e}")
        return []


# ------------------------------------------------
# Resume split by uploader
# ------------------------------------------------

def list_resumes_by_uploader(config, current_user):

    try:

        uploader = _make_uploader(config)

        items = uploader.list_files(
            config["site_id"],
            config["drive_id"],
            config["input_folder_path"]
        )

        my_resumes = []
        other_resumes = []

        for item in items:

            name = item.get("name", "")

            if not name.lower().endswith((".pdf", ".docx")):
                continue

            created_by = (
                item.get("createdBy", {})
                .get("user", {})
                .get("displayName", "")
            )

            entry = {
                "name": name,
                "item_id": item.get("id"),
                "created_by": created_by,
                "download_url": item.get("@microsoft.graph.downloadUrl")
            }

            if created_by.lower() == current_user.lower():
                my_resumes.append(entry)
            else:
                other_resumes.append(entry)

        return {
            "my_resumes": my_resumes,
            "other_resumes": other_resumes
        }

    except Exception as e:

        st.error(f"Could not list resumes: {e}")

        return {
            "my_resumes": [],
            "other_resumes": []
        }