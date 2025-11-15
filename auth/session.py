"""
Session management with hybrid permission system
Compatible with existing login.py implementation

VERSION HISTORY:
1.3.0 - Simplified to match farm-2-app pattern - 11/15/25
      CHANGES:
      - Renamed reset_password() to send_password_reset_email() for clarity
      - Kept complete_password_reset() for token-based password update
      - Matches farm-2-app's proven password reset pattern
1.2.0 - Added password reset completion - 11/15/25
      ADDITIONS:
      - Added complete_password_reset() method for updating password with token
      - Handles access_token from password reset email link
      - Validates and updates user password securely
1.1.0 - Added password reset functionality - 11/15/25
      ADDITIONS:
      - Added reset_password() method for sending password reset emails
      - Integration with Supabase Auth password reset
      - Logging for password reset requests
1.0.0 - Hybrid permission system with role-based and user-specific access - 11/11/25
KEY FUNCTIONS:
- Supabase Auth integration (sign in/sign out)
- Password reset functionality (request & complete)
- Hybrid permissions (Admin: all modules, User: custom access)
- Module access validation (has_module_access, require_module_access)
- Role checks (is_admin, is_manager)
- Session state management
- Activity logging for login/logout
- Profile and user info access
"""
import streamlit as st
from typing import Dict, List, Optional, Tuple
from config.database import Database, UserDB, ModuleDB, ActivityLogger


class SessionManager:
    """
    Manages user sessions and permissions
    Uses hybrid permission system:
    - Admins: Automatic access to all modules
    - Users: Check user_module_permissions table
    """
    
    @staticmethod
    def init_session():
        """Initialize session state variables"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'profile' not in st.session_state:
            st.session_state.profile = None
        if 'accessible_modules' not in st.session_state:
            st.session_state.accessible_modules = []
        if 'current_module' not in st.session_state:
            st.session_state.current_module = None
    
    @staticmethod
    def login(email: str, password: str) -> Tuple[bool, str]:
        """
        Handle user login with email and password
        Args:
            email: User's email
            password: User's password
        Returns:
            Tuple of (success: bool, error_message: str)
        """
        try:
            # Get Supabase client
            supabase = Database.get_client()
            
            # Attempt to sign in with Supabase Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not response.user:
                return False, "Invalid email or password"
            
            # Create user dict
            user_dict = {
                'id': response.user.id,
                'email': response.user.email
            }
            
            # Get user profile from database
            profile = UserDB.get_user_profile(user_dict['id'])
            
            if not profile:
                return False, "User profile not found. Please contact administrator."
            
            if not profile.get('is_active', False):
                return False, "Your account is inactive. Please contact administrator."
            
            # Set session state
            st.session_state.authenticated = True
            st.session_state.user = user_dict
            st.session_state.profile = profile
            
            # Load accessible modules using hybrid permissions
            st.session_state.accessible_modules = SessionManager._load_accessible_modules(
                user_dict['id'], 
                profile
            )
            
            # Log successful login
            ActivityLogger.log(
                user_id=user_dict['id'],
                action_type='login',
                module_key='auth',
                description=f"User {profile.get('full_name', user_dict['email'])} logged in"
            )
            
            return True, ""
            
        except Exception as e:
            error_message = str(e)

            # Handle specific Supabase auth errors
            if "Invalid login credentials" in error_message:
                return False, "Invalid email or password"
            elif "Email not confirmed" in error_message:
                return False, "Please verify your email address before logging in"
            elif "User not found" in error_message:
                return False, "No account found with this email"
            else:
                return False, f"Login failed: {error_message}"

    @staticmethod
    def send_password_reset_email(email: str) -> Tuple[bool, str]:
        """
        Send password reset email to user

        Args:
            email: User's email address

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get Supabase client
            supabase = Database.get_client()

            # Send password reset email
            supabase.auth.reset_password_email(email)

            # Log password reset request
            ActivityLogger.log(
                user_id=None,  # No user ID since not authenticated
                action_type='password_reset_request',
                module_key='auth',
                description=f"Password reset requested for {email}",
                metadata={'email': email}
            )

            return True, "Password reset email sent! Please check your inbox."

        except Exception as e:
            error_message = str(e)

            # Don't reveal if email exists for security
            # Return success message regardless to prevent email enumeration
            return True, "If an account exists with this email, you will receive a password reset link."

    @staticmethod
    def complete_password_reset(access_token: str, new_password: str) -> Tuple[bool, str]:
        """
        Complete password reset by updating the user's password

        Args:
            access_token: Access token from password reset email link
            new_password: New password to set

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get Supabase client
            supabase = Database.get_client()

            # Set the session with the access token
            supabase.auth.set_session(access_token, access_token)

            # Update the user's password
            response = supabase.auth.update_user({
                "password": new_password
            })

            if response.user:
                # Log password reset completion
                ActivityLogger.log(
                    user_id=response.user.id,
                    action_type='password_reset_complete',
                    module_key='auth',
                    description=f"Password reset completed for {response.user.email}",
                    metadata={'email': response.user.email}
                )

                return True, "Password updated successfully!"
            else:
                return False, "Failed to update password. Please try again."

        except Exception as e:
            error_message = str(e)

            # Handle specific errors
            if "Invalid" in error_message or "expired" in error_message.lower():
                return False, "Password reset link has expired. Please request a new one."
            else:
                return False, "Failed to update password. Please try again or contact support."

    @staticmethod
    def _load_accessible_modules(user_id: str, profile: Dict) -> List[Dict]:
        """
        Load modules user can access using hybrid permission system
        - Admins: Get all active modules
        - Users: Get modules from user_module_permissions via RPC
        """
        try:
            role_name = profile.get('role_name', '').lower()
            
            # Admins get all modules
            if role_name == 'admin':
                return ModuleDB.get_all_modules()
            
            # Users: Get modules via UserDB.get_user_modules RPC call
            else:
                return UserDB.get_user_modules(user_id)
                
        except Exception as e:
            st.error(f"Error loading modules: {str(e)}")
            return []
    
    @staticmethod
    def logout():
        """Handle user logout"""
        try:
            # Log logout action
            if st.session_state.get('user'):
                ActivityLogger.log(
                    user_id=st.session_state.user['id'],
                    action_type='logout',
                    module_key='auth',
                    description=f"User logged out"
                )
            
            # Clear session
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.profile = None
            st.session_state.accessible_modules = []
            st.session_state.current_module = None
            
        except Exception as e:
            st.error(f"Logout error: {str(e)}")
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated"""
        return st.session_state.get('authenticated', False)
    
    @staticmethod
    def is_logged_in() -> bool:
        """Check if user is logged in (alias for is_authenticated)"""
        return SessionManager.is_authenticated()
    
    @staticmethod
    def get_user() -> Optional[Dict]:
        """Get current user"""
        return st.session_state.get('user')
    
    @staticmethod
    def get_user_profile() -> Optional[Dict]:
        """Get current user profile"""
        return st.session_state.get('profile')
    
    @staticmethod
    def is_admin() -> bool:
        """Check if current user is admin"""
        profile = st.session_state.get('profile')
        if profile:
            return profile.get('role_name', '').lower() == 'admin'
        return False
    
    @staticmethod
    def is_manager() -> bool:
        """Check if current user is manager (legacy - now treated as user)"""
        profile = st.session_state.get('profile')
        if profile:
            role = profile.get('role_name', '').lower()
            return role == 'manager' or role == 'user'
        return False
    
    @staticmethod
    def get_accessible_modules() -> List[Dict]:
        """Get list of modules user can access"""
        return st.session_state.get('accessible_modules', [])
    
    @staticmethod
    def has_module_access(module_key: str) -> bool:
        """
        Check if user has access to a specific module
        Uses hybrid permission system
        """
        # Admin always has access
        if SessionManager.is_admin():
            return True
        
        # Check if module is in user's accessible modules
        accessible_modules = st.session_state.get('accessible_modules', [])
        return any(m.get('module_key') == module_key for m in accessible_modules)
    
    @staticmethod
    def require_module_access(module_key: str):
        """
        Require module access or stop execution
        Use this at the start of each module's show() function
        """
        if not SessionManager.has_module_access(module_key):
            st.error("⛔ Access Denied")
            st.warning("You don't have permission to access this module.")
            st.info("Contact your administrator if you need access.")
            st.stop()
    
    @staticmethod
    def require_admin():
        """Require admin access or stop execution"""
        if not SessionManager.is_admin():
            st.error("⛔ Admin Access Required")
            st.warning("This section is only accessible to administrators.")
            st.stop()
    
    @staticmethod
    def set_current_module(module_key: str):
        """Set the current active module"""
        st.session_state.current_module = module_key
    
    @staticmethod
    def get_current_module() -> Optional[str]:
        """Get the current active module key"""
        return st.session_state.get('current_module')
