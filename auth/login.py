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
        3. Contact your
