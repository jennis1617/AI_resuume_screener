"""
SharePoint Integration Module
"""

import streamlit as st
import io
from datetime import datetime

# SharePoint Integration (Optional) - FIXED
SHAREPOINT_AVAILABLE = False
SHAREPOINT_ERROR = None

try:
    import importlib
    import sys
    
    # Force reimport if already imported
    if 'office365.sharepoint.client_context' in sys.modules:
        importlib.reload(sys.modules['office365.sharepoint.client_context'])
    if 'office365.runtime.auth.user_credential' in sys.modules:
        importlib.reload(sys.modules['office365.runtime.auth.user_credential'])
    if 'office365.sharepoint.files.file' in sys.modules:
        importlib.reload(sys.modules['office365.sharepoint.files.file'])
    
    from office365.sharepoint.client_context import ClientContext
    from office365.runtime.auth.user_credential import UserCredential
    from office365.sharepoint.files.file import File
    SHAREPOINT_AVAILABLE = True
except ImportError as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = str(e)
except Exception as e:
    SHAREPOINT_AVAILABLE = False
    SHAREPOINT_ERROR = f"Unexpected error: {str(e)}"

def connect_to_sharepoint(site_url, username, password):
    """Connect to SharePoint and return context - FIXED VERSION."""
    try:
        # Use UserCredential for username/password authentication
        credentials = UserCredential(username, password)
        ctx = ClientContext(site_url).with_credentials(credentials)
        
        # Test the connection
        web = ctx.web
        ctx.load(web)
        ctx.execute_query()
        
        return ctx
    except Exception as e:
        st.error(f"SharePoint connection error: {str(e)}")
        return None

def upload_to_sharepoint(ctx, folder_path, file_content, file_name):
    """Upload file to SharePoint."""
    try:
        target_folder = ctx.web.get_folder_by_server_relative_url(folder_path)
        target_folder.upload_file(file_name, file_content).execute_query()
        return True
    except Exception as e:
        st.error(f"Upload error: {str(e)}")
        return False

def download_from_sharepoint(ctx, folder_path):
    """Download all resumes from SharePoint folder."""
    try:
        folder = ctx.web.get_folder_by_server_relative_url(folder_path)
        files = folder.files
        ctx.load(files)
        ctx.execute_query()
        
        downloaded_files = []
        for file in files:
            file_url = file.properties["ServerRelativeUrl"]
            file_name = file.properties["Name"]
            
            # Download file
            response = File.open_binary(ctx, file_url)
            
            # Get file timestamp from SharePoint
            time_created = file.properties.get("TimeCreated", datetime.now().isoformat())
            
            downloaded_files.append({
                'name': file_name,
                'content': response.content,
                'timestamp': time_created
            })
        
        return downloaded_files
    except Exception as e:
        st.error(f"Download error: {str(e)}")
        return []

def save_csv_to_sharepoint(ctx, folder_path, df, filename):
    """Save DataFrame as CSV to SharePoint."""
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        
        return upload_to_sharepoint(ctx, folder_path, csv_bytes, filename)
    except Exception as e:
        st.error(f"Error saving CSV to SharePoint: {str(e)}")
        return False