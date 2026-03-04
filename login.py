"""
Dummy Login Page — for demo purposes only.
Shows how a real login system would work in production.
In a real deployment this would authenticate against Azure AD / company SSO.
"""

import streamlit as st

# ── Dummy user accounts (demo only) ──────────────────────────────────────────
# In production these would come from Azure AD or a secure database.
DEMO_USERS = {
    "hr.lead@nexturn.com":    {"password": "nexturn123", "name": "HR Lead",       "role": "HR Head"},
    "recruiter@nexturn.com":  {"password": "recruit123", "name": "Mehali Sharma", "role": "Recruiter"},
    "admin@nexturn.com":      {"password": "admin123",   "name": "Admin User",    "role": "Admin"},
}


def render_login_page():
    """Render the login screen. Returns True if user is authenticated."""

    # ── Already logged in — skip ──────────────────────────────────────────────
    if st.session_state.get('logged_in'):
        return True

    # ── Login card — logo + title ─────────────────────────────────────────────
    _, logo_col, _ = st.columns([2, 1, 2])
    with logo_col:
        st.image("logo.png", width=200)

    st.markdown(
        "<h1 style='text-align:center; font-size:2.4rem; font-weight:900; "
        "letter-spacing:-0.5px; color:#0f172a; margin-bottom:4px;'>Resume Screening System</h1>"
        "<p style='text-align:center; color:#64748b; font-size:1rem; margin-top:0; margin-bottom:24px;'>"
        "Powered by Groq | Automated Intelligent Recruitment</p>"
        "<hr style='border:none; border-top:2px solid #e2e8f0; margin-bottom:28px;'>",
        unsafe_allow_html=True
    )

    # Centre the form using columns
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("#### 🔐 Sign In")
        email    = st.text_input("Email address",    placeholder="you@nexturn.com",  key="login_email")
        password = st.text_input("Password",         placeholder="••••••••",         type="password", key="login_password")

        if st.button("Sign In", type="primary", use_container_width=True):
            user = DEMO_USERS.get(email.strip().lower())
            if user and user["password"] == password:
                st.session_state['logged_in']    = True
                st.session_state['user_name']    = user["name"]
                st.session_state['user_role']    = user["role"]
                st.session_state['user_email']   = email.strip().lower()
                st.rerun()
            else:
                st.error("❌ Incorrect email or password. Please try again.")

        st.markdown("""
        <div style="margin-top:20px; padding:12px 14px; background:#F0F9FF;
                    border-radius:8px; font-size:0.82rem; color:#1E40AF;">
            <strong>Demo accounts:</strong><br>
            hr.lead@nexturn.com &nbsp;/&nbsp; nexturn123<br>
            recruiter@nexturn.com &nbsp;/&nbsp; recruit123
        </div>
        """, unsafe_allow_html=True)

    return False


def render_user_badge():
    """Show logged-in user info in the sidebar with a logout button."""
    name  = st.session_state.get('user_name',  'User')
    role  = st.session_state.get('user_role',  '')
    email = st.session_state.get('user_email', '')

    st.sidebar.markdown(
        f"<div style='background:#F0FDF4; border:1px solid #86EFAC; border-radius:8px; "
        f"padding:10px 12px; margin-bottom:12px;'>"
        f"<p style='margin:0; font-size:0.95rem; font-weight:700; color:#166534;'>👤 {name}</p>"
        f"<p style='margin:2px 0 0 0; font-size:0.8rem; color:#555;'>{role} · {email}</p>"
        f"</div>",
        unsafe_allow_html=True
    )
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        for key in ['logged_in', 'user_name', 'user_role', 'user_email']:
            st.session_state.pop(key, None)
        st.rerun()