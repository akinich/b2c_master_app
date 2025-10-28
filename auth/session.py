"""
Session management for user authentication
"""
import streamlit as st
from typing import Optional, Dict
from config.database import UserDB, ActivityLogger

class SessionManager:
    """Manages user sessions in Streamlit"""
    
    @staticmethod
    def initialize_session():
        """Initialize session state variables"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'user_profile' not in st.session_state:
            st.session_state.user_profile = None
        if 'accessible_modules' not in st.session_state:
            st.session_state.accessible_modules = []
        if 'current_module' not in st.session_state:
            st.session_state.current_module = None
    
    @staticmethod
    def login(user: Dict) -> bool:
        """
        Login user and load their profile
        Args:
            user: Dictionary containing user info from Supabase auth
        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            user_id = user.get('id')
            email = user.get('email')
            
            # Get user profile with role
            profile = UserDB.get_user_profile(user_id)
            
            if not profile:
                st.error("User profile not found. Please contact administrator.")
                return False
            
            if not profile.get('is_active'):
                st.error("Your account has been deactivated. Please contact administrator.")
                return False
            
            # Get accessible modules
            modules = UserDB.get_user_modules(user_id)
            
            # Set session state
            st.session_state.authenticated = True
            st.session_state.user = {
                'id': user_id,
                'email': email
            }
            st.session_state.user_profile = profile
            st.session_state.accessible_modules = modules
            st.session_state.current_module = None
            
            # Log login activity
            ActivityLogger.log(
                user_id=user_id,
                action_type='login',
                description=f"User {email} logged in successfully"
            )
            
            return True
            
        except Exception as e:
            st.error(f"Login error: {str(e)}")
            return False
    
    @staticmethod
    def logout():
        """Logout user and clear session"""
        if st.session_state.get('authenticated'):
            user_id = st.session_state.user.get('id')
            email = st.session_state.user.get('email')
            
            # Log logout activity
            ActivityLogger.log(
                user_id=user_id,
                action_type='logout',
                description=f"User {email} logged out"
            )
        
        # Clear all session state
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.user_profile = None
        st.session_state.accessible_modules = []
        st.session_state.current_module = None
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated"""
        return st.session_state.get('authenticated', False)
    
    @staticmethod
    def get_user() -> Optional[Dict]:
        """Get current user info"""
        return st.session_state.get('user')
    
    @staticmethod
    def get_user_profile() -> Optional[Dict]:
        """Get current user profile with role"""
        return st.session_state.get('user_profile')
    
    @staticmethod
    def get_user_role() -> Optional[str]:
        """Get current user's role name"""
        profile = SessionManager.get_user_profile()
        return profile.get('role_name') if profile else None
    
    @staticmethod
    def is_admin() -> bool:
        """Check if current user is admin"""
        return SessionManager.get_user_role() == 'Admin'
    
    @staticmethod
    def is_manager() -> bool:
        """Check if current user is manager"""
        return SessionManager.get_user_role() == 'Manager'
    
    @staticmethod
    def get_accessible_modules() -> list:
        """Get list of modules accessible to current user"""
        return st.session_state.get('accessible_modules', [])
    
    @staticmethod
    def can_access_module(module_key: str) -> bool:
        """Check if user can access a specific module"""
        modules = SessionManager.get_accessible_modules()
        return any(m.get('module_key') == module_key for m in modules)
    
    @staticmethod
    def set_current_module(module_key: str):
        """Set the currently active module"""
        if SessionManager.can_access_module(module_key):
            st.session_state.current_module = module_key
            
            # Log module access
            user = SessionManager.get_user()
            if user:
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='module_access',
                    module_key=module_key,
                    description=f"User accessed module: {module_key}"
                )
    
    @staticmethod
    def get_current_module() -> Optional[str]:
        """Get the currently active module key"""
        return st.session_state.get('current_module')
    
    @staticmethod
    def require_auth():
        """Decorator-like function to require authentication"""
        if not SessionManager.is_authenticated():
            st.warning("Please log in to access this page.")
            st.stop()
    
    @staticmethod
    def require_admin():
        """Require admin role for access"""
        SessionManager.require_auth()
        if not SessionManager.is_admin():
            st.error("Access denied. Admin privileges required.")
            st.stop()
    
    @staticmethod
    def require_module_access(module_key: str):
        """Require access to a specific module"""
        SessionManager.require_auth()
        if not SessionManager.can_access_module(module_key):
            st.error(f"Access denied. You don't have permission to access this module.")
            st.stop()
