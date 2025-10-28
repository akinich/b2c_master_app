"""
Login page and authentication handling
"""
import streamlit as st
from config.database import Database
from auth.session import SessionManager

def show_login_page():
    """Display the login page"""
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🔐 Login")
        st.markdown("---")
        
        # Check if showing forgot password form
        if st.session_state.get('show_forgot_password', False):
            show_forgot_password_form()
        else:
            show_login_form()


def show_login_form():
    """Show the main login form"""
    # Login form
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="your@email.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password")
            else:
                handle_login(email, password)
    
    # Forgot password link
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Forgot Password?", use_container_width=True):
            st.session_state.show_forgot_password = True
            st.rerun()
    
    with col2:
        st.caption("Contact admin for account")
    
    st.markdown("---")
    st.caption("Don't have an account? Contact your administrator.")


def show_forgot_password_form():
    """Show forgot password form"""
    st.markdown("### 🔑 Reset Password")
    st.info("Enter your email to receive password reset instructions")
    
    with st.form("forgot_password_form"):
        email = st.text_input("Email", placeholder="your@email.com")
        submit = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")
        
        if submit:
            if not email:
                st.error("Please enter your email")
            else:
                handle_forgot_password(email)
    
    # Back to login
    if st.button("← Back to Login", use_container_width=True):
        st.session_state.show_forgot_password = False
        st.rerun()


def handle_forgot_password(email: str):
    """Handle password reset request"""
    try:
        supabase = Database.get_client()
        
        # Send password reset email
        supabase.auth.reset_password_email(email)
        
        st.success("✅ Password reset instructions sent!")
        st.info("""
        Check your email for password reset instructions.
        
        If you don't receive an email:
        1. Check your spam folder
        2. Verify the email address is correct
        3. Contact your administrator for assistance
        """)
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle common errors
        if "rate limit" in error_msg.lower():
            st.error("Too many reset attempts. Please wait a few minutes and try again.")
        elif "not found" in error_msg.lower():
            st.warning("If an account exists with this email, you will receive reset instructions.")
        else:
            st.error("Unable to send reset email. Please contact your administrator.")


def handle_login(email: str, password: str):
    """
    Handle login authentication with Supabase
    """
    try:
        with st.spinner("Logging in..."):
            # Get Supabase client
            supabase = Database.get_client()
            
            # Attempt to sign in with Supabase Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Login successful, create session
                user_dict = {
                    'id': response.user.id,
                    'email': response.user.email
                }
                
                if SessionManager.login(user_dict):
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Failed to load user profile. Please contact administrator.")
            else:
                st.error("Invalid email or password")
                
    except Exception as e:
        error_message = str(e)
        
        # Handle specific Supabase auth errors
        if "Invalid login credentials" in error_message:
            st.error("Invalid email or password")
        elif "Email not confirmed" in error_message:
            st.error("Please verify your email address before logging in")
        elif "User not found" in error_message:
            st.error("No account found with this email")
        else:
            st.error(f"Login failed: {error_message}")


def show_logout_button():
    """Display logout button in sidebar"""
    if st.sidebar.button("🚪 Logout", use_container_width=True):
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
