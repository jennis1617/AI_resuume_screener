import streamlit as st
import os

ALLOWED_DOMAIN = "@nexturn.com"
JD_FOLDER_PATH = "Demair/Job_Descriptions"  # replace with your actual path

# -------------------------------
# Helper: Format username
# -------------------------------
def format_username(email: str):
    username = email.split("@")[0].replace(".", " ")
    return username.title()

# -------------------------------
# Fetch JDs
# -------------------------------
def fetch_jds(folder_path: str):
    if not os.path.exists(folder_path):
        st.error(f"JD folder not found: {folder_path}")
        return []

    # List all PDFs and DOCX files
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".docx"))]
    return files

# -------------------------------
# Login Page
# -------------------------------
def login_page():
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "user_email" not in st.session_state:
        st.session_state["user_email"] = None

    # Center logo
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("logo.png", width=180)

    st.title("🔐 HR Login")

    email = st.text_input("Enter your company email")

    if st.button("Login"):
        if not email:
            st.warning("Please enter your email.")
            return
        if not email.endswith(ALLOWED_DOMAIN):
            st.error("Access allowed only for company email accounts")
            return

        username = format_username(email)
        st.session_state["user"] = username
        st.session_state["user_email"] = email
        st.success(f"Welcome {username}")
        st.experimental_rerun()  # Refresh to show JD dashboard

# -------------------------------
# Logout
# -------------------------------
def logout():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.success("Logged out successfully")
        st.experimental_rerun()

# -------------------------------
# JD Dashboard
# -------------------------------
def jd_dashboard():
    st.sidebar.write(f"👤 Logged in as: {st.session_state['user']}")
    logout()

    st.header("📂 Available Job Descriptions")

    jds = fetch_jds(JD_FOLDER_PATH)
    if not jds:
        st.info("No JDs available.")
    else:
        for jd in jds:
            st.write(f"- {jd}")

# -------------------------------
# Main
# -------------------------------
def main():
    if "user" not in st.session_state or st.session_state["user"] is None:
        login_page()
    else:
        jd_dashboard()

if __name__ == "__main__":
    main()