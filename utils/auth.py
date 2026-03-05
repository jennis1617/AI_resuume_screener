import streamlit as st

ALLOWED_DOMAIN = "@nexturn.com"

# -------------------------------
# Helper: Format username
# -------------------------------
def format_username(email: str):
    """
    Convert email username to readable name
    Example:
    kavitha.mohan@nexturn.com -> Kavitha Mohan
    """
    username = email.split("@")[0]
    username = username.replace(".", " ")
    username = username.title()
    return username


# -------------------------------
# Login Page
# -------------------------------
def login_page():

    # Initialize session keys safely
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

        # Save user info in session
        st.session_state["user"] = username
        st.session_state["user_email"] = email

        st.success(f"Welcome {username}")
        st.rerun()


# -------------------------------
# Logout
# -------------------------------
def logout():

    if st.sidebar.button("Logout"):

        st.session_state.clear()

        st.success("Logged out successfully")

        st.rerun()