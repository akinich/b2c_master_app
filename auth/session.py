"""
Session management for user authentication and access control
UPDATED FOR HYBRID PERMISSION SYSTEM (Admin + User with module-level permissions)
"""
import streamlit as st
from typing import Optional, Dict, List
from config.database import Database, UserDB, UserPermissionDB, ActivityLogger

class SessionManager:
    """Manages user session, authentication state, and access control"""
    
    @staticmethod
    def init_session():
        """Initialize session state variables"""
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'user_profile' not in st.session_state:
            st.session_state.user_profile = None
        if 'accessible_modules' not in st.session_state:
            st.session_state.accessible_modules = []
        if 'current_module' not in st.session_state:
            st.session_state.current_module = 'dashboard'
    
    @staticmethod
    def login(email: str, password: str) -> tuple[bool, Optional[str]]:
        """
        Authenticate user with Supabase
        Returns: (success: bool, error_message: Optional[str])
        """
        try:
            db = Database.get_client()
            
            # Authenticate with Supabase
            response = db.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                user = response.user
                
                # Load user profile
                profile = UserDB.get_user_profile(user.id)
                
                if not profile:
                    return False, "User profile not found. Please contact administrator."
                
                if not profile.get('is_active', False):
                    return False, "Your account has been deactivated. Please contact administrator."
                
                # Set user in session
                SessionManager.set_user(user.model_dump())
                
                # Log successful login
                ActivityLogger.log(
                    user_id=user.id,
                    action_type='login',
                    description=f"User {email} logged in successfully"
                )
                
                return True, None
            else:
                return False, "Invalid email or password"
                
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific Supabase auth errors
            if "Invalid login credentials" in error_msg:
                return False, "Invalid email or password"
            elif "Email not confirmed" in error_msg:
                return False, "Please verify your email address before logging in"
            elif "User not found" in error_msg:
                return False, "No account found with this email"
            else:
                return False, f"Login failed: {error_msg}"
    
    @staticmethod
    def logout():
        """Log out current user"""
        try:
            user = SessionManager.get_user()
            if user:
                # Log logout activity
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='logout',
                    description=f"User {user.get('email')} logged out"
                )
            
            # Sign out from Supabase
            db = Database.get_client()
            db.auth.sign_out()
            
        except Exception as e:
            # Continue with local logout even if Supabase logout fails
            print(f"Error during Supabase logout: {str(e)}")
        
        finally:
            # Clear session state
            SessionManager.clear_session()
    
    @staticmethod
    def is_logged_in() -> bool:
        """Check if user is logged in"""
        return st.session_state.get('user') is not None
    
    @staticmethod
    def get_user() -> Optional[Dict]:
        """Get current user from session"""
        return st.session_state.get('user')
    
    @staticmethod
    def get_user_profile() -> Optional[Dict]:
        """Get user profile with role information"""
        return st.session_state.get('user_profile')
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get current user ID"""
        user = SessionManager.get_user()
        return user.get('id') if user else None
    
    @staticmethod
    def get_role() -> Optional[str]:
        """Get user role (lowercase: 'admin' or 'user')"""
        profile = SessionManager.get_user_profile()
        if profile:
            return profile.get('role_name', '').lower()
        return None
    
    @staticmethod
    def is_admin() -> bool:
        """Check if current user is admin"""
        return SessionManager.get_role() == 'admin'
    
    @staticmethod
    def is_user() -> bool:
        """Check if current user is a regular user (non-admin)"""
        return SessionManager.get_role() == 'user'
    
    @staticmethod
    def set_user(user: Dict):
        """Set logged in user"""
        st.session_state.user = user
        
        # Load user profile
        profile = UserDB.get_user_profile(user['id'])
        st.session_state.user_profile = profile
        
        # Load accessible modules (hybrid permission check)
        modules = UserDB.get_user_modules(user['id'])
        st.session_state.accessible_modules = modules
    
    @staticmethod
    def clear_session():
        """Clear all session data (logout)"""
        st.session_state.user = None
        st.session_state.user_profile = None
        st.session_state.accessible_modules = []
        st.session_state.current_module = 'dashboard'
    
    @staticmethod
    def get_accessible_modules() -> List[Dict]:
        """Get list of modules accessible to current user"""
        return st.session_state.get('accessible_modules', [])
    
    @staticmethod
    def has_module_access(module_key: str) -> bool:
        """
        Check if current user has access to a specific module
        HYBRID PERMISSION CHECK:
        - Admins: Always have access to all modules
        - Users: Check user_module_permissions
        """
        # Admin has access to everything
        if SessionManager.is_admin():
            return True
        
        # Check if module is in accessible modules list
        modules = SessionManager.get_accessible_modules()
        return any(m.get('module_key') == module_key for m in modules)
    
    @staticmethod
    def require_access(module_key: str):
        """
        Require module access, stop execution if not authorized
        Use this at the start of module run() functions
        """
        if not SessionManager.has_module_access(module_key):
            st.error("🚫 You don't have access to this module.")
            st.info("Contact your administrator to request access.")
            st.stop()
    
    @staticmethod
    def require_admin():
        """Require admin role, stop execution if not admin"""
        if not SessionManager.is_admin():
            st.error("🚫 Admin access required.")
            st.info("This page is only accessible to administrators.")
            st.stop()
    
    @staticmethod
    def require_login():
        """Require user to be logged in, redirect to login if not"""
        if not SessionManager.is_logged_in():
            st.warning("⚠️ Please log in to continue")
            st.stop()
    
    @staticmethod
    def set_current_module(module_key: str):
        """Set the currently active module"""
        st.session_state.current_module = module_key
    
    @staticmethod
    def get_current_module() -> str:
        """Get the currently active module"""
        return st.session_state.get('current_module', 'dashboard')
    
    @staticmethod
    def refresh_permissions():
        """
        Refresh user's module permissions
        Call this after admin changes permissions
        """
        user = SessionManager.get_user()
        if user:
            modules = UserDB.get_user_modules(user['id'])
            st.session_state.accessible_modules = modules
    
    @staticmethod
    def log_activity(action_type: str, module_key: str = None, 
                    description: str = None, metadata: Dict = None,
                    success: bool = True):
        """
        Log user activity
        Convenience method for activity logging
        """
        user_id = SessionManager.get_user_id()
        if user_id:
            ActivityLogger.log(
                user_id=user_id,
                action_type=action_type,
                module_key=module_key,
                description=description,
                metadata=metadata,
                success=success
            )
    
    # ==========================================
    # BACKWARDS COMPATIBILITY METHODS
    # ==========================================
    # These methods maintain compatibility with old code
    # that used 'manager' role
    
    @staticmethod
    def is_manager() -> bool:
        """
        DEPRECATED: Manager role no longer exists
        Returns False for compatibility
        """
        return False
    
    @staticmethod
    def has_role(role_name: str) -> bool:
        """
        Check if user has a specific role
        Only 'admin' and 'user' are valid now
        """
        current_role = SessionManager.get_role()
        return current_role == role_name.lower()
    
    @staticmethod
    def can_manage_users() -> bool:
        """Check if user can manage other users (admin only)"""
        return SessionManager.is_admin()
    
    @staticmethod
    def can_view_logs() -> bool:
        """Check if user can view activity logs (admin only)"""
        return SessionManager.is_admin()
    
    @staticmethod
    def can_manage_permissions() -> bool:
        """Check if user can manage permissions (admin only)"""
        return SessionManager.is_admin()
