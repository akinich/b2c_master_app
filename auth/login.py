"""
Login page and authentication UI

VERSION HISTORY:
1.2.0 - Added password reset completion handler - 11/15/25
      ADDITIONS:
      - Added show_password_reset_completion() for handling reset tokens
      - Integration with Supabase Auth update user password
      - Handles redirect from static/redirect.html after email link click
      - Query parameter detection for reset_password flow
1.1.0 - Added password reset functionality - 11/15/25
      ADDITIONS:
      - Added "Forgot Password?" link on login page
      - Password reset form with email input
      - Integration with SessionManager.reset_password()
      - User-friendly password reset flow
1.0.1 - Added login rate limiting - 11/12/25
      SECURITY IMPROVEMENTS:
      - Added rate limiting (5 attempts, 5-minute lockout)
      - Prevents brute force attacks
      - Shows remaining attempts to user
1.0.0 - Login page with Supabase authentication - 11/11/25
KEY FUNCTIONS:
- Email/password login form
- Password reset functionality
- Password reset completion (new password entry)
- Integration with SessionManager for auth
- Logout button for sidebar
- User info display (name, email, role)
- Error handling with user-friendly messages
"""
import streamlit as st
from auth.session import SessionManager
from utils.rate_limiter import LoginRateLimiter

def show_login_page():
    """Display login page with login and password reset options"""

    # Initialize session state for password reset toggle
    if 'show_reset_form' not in st.session_state:
        st.session_state.show_reset_form = False

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("# 🔐 Login")
        st.markdown("---")

        # Show either login form or password reset form
        if not st.session_state.show_reset_form:
            # Login Form
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="your.email@company.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login", width='stretch', type="primary")

                if submit:
                    if not email or not password:
                        st.error("Please enter both email and password")
                    else:
                        handle_login(email, password)

            # Forgot Password Link
            st.markdown("---")
            if st.button("🔑 Forgot Password?", use_container_width=True):
                st.session_state.show_reset_form = True
                st.rerun()

        else:
            # Password Reset Form
            st.markdown("### 🔑 Reset Password")
            st.info("Enter your email address and we'll send you a link to reset your password.")

            with st.form("reset_form"):
                reset_email = st.text_input("Email", placeholder="your.email@company.com")
                submit_reset = st.form_submit_button("Send Reset Link", width='stretch', type="primary")

                if submit_reset:
                    if not reset_email:
                        st.error("Please enter your email address")
                    else:
                        handle_password_reset(reset_email)

            # Back to Login Link
            st.markdown("---")
            if st.button("← Back to Login", use_container_width=True):
                st.session_state.show_reset_form = False
                st.rerun()


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


def handle_password_reset(email: str):
    """
    Handle password reset request

    Args:
        email: User's email address

    Sends a password reset email via Supabase Auth
    """
    with st.spinner("Sending reset link..."):
        success, message = SessionManager.reset_password(email)

        if success:
            st.success(f"✅ {message}")
            st.info("💡 Check your spam folder if you don't see the email in a few minutes.")
        else:
            st.error(f"❌ {message}")


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


def show_password_reset_completion():
    """
    Display password reset completion page for users who clicked the reset link

    This page is shown when users return to the app after clicking the password
    reset link in their email. They can enter their new password here.
    """
    # Center the form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("# 🔐 Set New Password")
        st.markdown("---")
        st.info("Please enter your new password below.")

        with st.form("new_password_form"):
            new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
            submit = st.form_submit_button("Update Password", width='stretch', type="primary")

            if submit:
                if not new_password or not confirm_password:
                    st.error("Please enter both password fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters long")
                else:
                    handle_password_update(new_password)


def handle_password_update(new_password: str):
    """
    Handle password update after reset

    Args:
        new_password: The new password to set

    Uses the access_token from query parameters to update the user's password
    """
    # Get access token from query parameters
    query_params = st.query_params
    access_token = query_params.get('access_token')

    if not access_token:
        st.error("❌ Invalid or expired reset link. Please request a new password reset.")
        return

    with st.spinner("Updating password..."):
        success, message = SessionManager.complete_password_reset(access_token, new_password)

        if success:
            st.success(f"✅ {message}")
            st.info("🔑 You can now log in with your new password.")

            # Clear query parameters
            st.query_params.clear()

            # Wait a moment then redirect to login
            import time
            time.sleep(2)
            st.rerun()
        else:
            st.error(f"❌ {message}")
