"""
Login page and authentication UI

VERSION HISTORY:
1.0.1 - Added login rate limiting - 11/12/25
      SECURITY IMPROVEMENTS:
      - Added rate limiting (5 attempts, 5-minute lockout)
      - Prevents brute force attacks
      - Shows remaining attempts to user
1.0.0 - Login page with Supabase authentication - 11/11/25
KEY FUNCTIONS:
- Email/password login form
- Integration with SessionManager for auth
- Logout button for sidebar
- User info display (name, email, role)
- Error handling with user-friendly messages
"""
import streamlit as st
from auth.session import SessionManager
from utils.rate_limiter import LoginRateLimiter

def show_login_page():
    """Display login page"""
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🔐 Login")
        st.markdown("---")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="your.email@company.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", width='stretch', type="primary")
            
            if submit:
                if not email or not password:
                    st.error("Please enter both email and password")
                else:
                    handle_login(email, password)


def handle_login(email: str, password: str):
    """
    Handle login attempt with rate limiting

    Args:
        email: User's email
        password: User's password

    Security:
        - Checks if account is locked out
        - Records failed attempts
        - Displays remaining attempts
        - Locks out after MAX_ATTEMPTS failures
    """
    # SECURITY: Check if account is locked out
    if LoginRateLimiter.is_locked_out(email):
        lockout_message = LoginRateLimiter.format_lockout_message(email)
        st.error(f"❌ {lockout_message}")
        st.warning("⏳ Please wait before trying again")
        return

    with st.spinner("Logging in..."):
        success, error_message = SessionManager.login(email, password)

        if success:
            # SECURITY: Clear failed attempts on successful login
            LoginRateLimiter.record_successful_login(email)
            st.success("✅ Login successful! Redirecting...")
            st.rerun()
        else:
            # SECURITY: Record failed attempt
            LoginRateLimiter.record_failed_attempt(email)
            remaining = LoginRateLimiter.get_remaining_attempts(email)

            if remaining > 0:
                st.error(f"❌ {error_message}")
                if remaining <= 2:  # Warn when few attempts remain
                    st.warning(f"⚠️ {remaining} attempt(s) remaining before temporary lockout")
            else:
                lockout_message = LoginRateLimiter.format_lockout_message(email)
                st.error(f"❌ {lockout_message}")


def show_logout_button():
    """Display logout button in sidebar"""
    if st.sidebar.button("🚪 Logout", width='stretch'):
        SessionManager.logout()
        st.rerun()


def show_user_info():
    """Display current user info in sidebar"""
    profile = SessionManager.get_user_profile()
    user = SessionManager.get_user()
    
    if profile and user:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 👤 User Info")
        st.sidebar.write(f"**Name:** {profile.get('full_name', 'N/A')}")
        st.sidebar.write(f"**Email:** {user.get('email')}")
        st.sidebar.write(f"**Role:** {profile.get('role_name', 'N/A')}")
        st.sidebar.markdown("---")
