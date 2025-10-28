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
        
        st.markdown("---")
        st.caption("Don't have an account? Contact your administrator.")


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
