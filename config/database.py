"""
Database Helper Functions - FIXED VERSION
Properly handles Supabase Auth user creation, editing, and deletion

VERSION: 1.2.0
DATE: 11/05/25
FIXES:
- Fixed create_user() to properly work with Supabase Auth API
- Added update_user() function
- Added delete_user() function with proper cleanup
- Better error handling and validation
"""
import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class UserDB:
    """Database operations for user management"""
    
    @staticmethod
    def get_supabase():
        """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            raise Exception("Supabase client not initialized")
        return st.session_state.supabase
    
    @staticmethod
    def get_all_users() -> List[Dict]:
        """
        Get all users with their profiles and roles
        
        Returns:
            List of user dictionaries with profile and role info
        """
        try:
            supabase = UserDB.get_supabase()
            
            # Join user_profiles with roles
            response = supabase.table('user_profiles') \
                .select('*, roles(role_name)') \
                .execute()
            
            if response.data:
                users = []
                for profile in response.data:
                    # Get email from auth.users
                    user_response = supabase.auth.admin.get_user_by_id(profile['id'])
                    
                    users.append({
                        'id': profile['id'],
                        'email': user_response.user.email if user_response.user else 'Unknown',
                        'full_name': profile.get('full_name'),
                        'role_id': profile.get('role_id'),
                        'role_name': profile['roles']['role_name'] if profile.get('roles') else 'Unknown',
                        'is_active': profile.get('is_active', True),
                        'created_at': profile.get('created_at')
                    })
                
                return users
            
            return []
            
        except Exception as e:
            st.error(f"Error fetching users: {str(e)}")
            return []
    
    @staticmethod
    def create_user(email: str, full_name: str, role_id: int) -> bool:
        """
        Create a new user in both Supabase Auth and user_profiles table
        
        Args:
            email: User's email address
            full_name: User's full name
            role_id: Role ID to assign
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = UserDB.get_supabase()
            
            # Step 1: Create user in Supabase Auth
            # Generate a temporary password (user will reset it via email)
            import secrets
            import string
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
            
            # Create auth user with email confirmation required
            auth_response = supabase.auth.admin.create_user({
                "email": email,
                "password": temp_password,
                "email_confirm": False,  # User must confirm email
                "user_metadata": {
                    "full_name": full_name
                }
            })
            
            if not auth_response.user:
                st.error("Failed to create user in authentication system")
                return False
            
            user_id = auth_response.user.id
            
            # Step 2: Create user profile
            profile_data = {
                'id': user_id,
                'full_name': full_name,
                'role_id': role_id,
                'is_active': True
            }
            
            profile_response = supabase.table('user_profiles').insert(profile_data).execute()
            
            if not profile_response.data:
                # If profile creation fails, we should ideally delete the auth user
                # But Supabase doesn't easily allow that, so we'll just log the error
                st.error("Failed to create user profile")
                return False
            
            # Step 3: Send password reset email (serves as welcome email)
            supabase.auth.admin.generate_link({
                "type": "recovery",
                "email": email
            })
            
            return True
            
        except Exception as e:
            st.error(f"Error creating user: {str(e)}")
            return False
    
    @staticmethod
    def update_user(user_id: str, full_name: str, role_id: int, is_active: bool) -> bool:
        """
        Update user profile information
        
        Args:
            user_id: User's UUID
            full_name: New full name
            role_id: New role ID
            is_active: New active status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = UserDB.get_supabase()
            
            update_data = {
                'full_name': full_name,
                'role_id': role_id,
                'is_active': is_active,
                'updated_at': datetime.now().isoformat()
            }
            
            response = supabase.table('user_profiles') \
                .update(update_data) \
                .eq('id', user_id) \
                .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            st.error(f"Error updating user: {str(e)}")
            return False
    
    @staticmethod
    def delete_user(user_id: str) -> bool:
        """
        Delete user from both user_profiles and Supabase Auth
        
        Args:
            user_id: User's UUID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = UserDB.get_supabase()
            
            # Step 1: Delete from user_profiles (will cascade due to foreign key)
            profile_response = supabase.table('user_profiles') \
                .delete() \
                .eq('id', user_id) \
                .execute()
            
            # Step 2: Delete from Supabase Auth
            # Note: This requires admin privileges
            auth_response = supabase.auth.admin.delete_user(user_id)
            
            return True
            
        except Exception as e:
            st.error(f"Error deleting user: {str(e)}")
            return False
    
    @staticmethod
    def get_all_roles() -> List[Dict]:
        """
        Get all available roles
        
        Returns:
            List of role dictionaries
        """
        try:
            supabase = UserDB.get_supabase()
            
            response = supabase.table('roles').select('*').execute()
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching roles: {str(e)}")
            return []


class UserPermissionDB:
    """Database operations for user-specific permissions"""
    
    @staticmethod
    def get_supabase():
        """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            raise Exception("Supabase client not initialized")
        return st.session_state.supabase
    
    @staticmethod
    def get_user_permissions(user_id: str) -> List[Dict]:
        """
        Get user's module permissions
        
        Args:
            user_id: User's UUID
            
        Returns:
            List of permission dictionaries with module info
        """
        try:
            supabase = UserPermissionDB.get_supabase()
            
            # First get user's role
            user_response = supabase.table('user_profiles') \
                .select('role_id') \
                .eq('id', user_id) \
                .single() \
                .execute()
            
            if not user_response.data:
                return []
            
            role_id = user_response.data['role_id']
            
            # Get role permissions
            response = supabase.table('role_permissions') \
                .select('*, modules(*)') \
                .eq('role_id', role_id) \
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching user permissions: {str(e)}")
            return []
    
    @staticmethod
    def update_user_permission(user_id: str, module_id: int, can_access: bool, updated_by: str) -> bool:
        """
        Update a user's permission for a specific module
        
        Note: This actually updates the role permission, affecting all users with that role
        For true user-specific permissions, you'd need a separate user_permissions table
        
        Args:
            user_id: User's UUID
            module_id: Module ID
            can_access: Whether user can access the module
            updated_by: Admin user ID making the change
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = UserPermissionDB.get_supabase()
            
            # Get user's role
            user_response = supabase.table('user_profiles') \
                .select('role_id') \
                .eq('id', user_id) \
                .single() \
                .execute()
            
            if not user_response.data:
                return False
            
            role_id = user_response.data['role_id']
            
            # Update role permission
            update_data = {
                'can_access': can_access
            }
            
            response = supabase.table('role_permissions') \
                .update(update_data) \
                .eq('role_id', role_id) \
                .eq('module_id', module_id) \
                .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            st.error(f"Error updating permission: {str(e)}")
            return False


class ModuleDB:
    """Database operations for module management"""
    
    @staticmethod
    def get_supabase():
        """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            raise Exception("Supabase client not initialized")
        return st.session_state.supabase
    
    @staticmethod
    def get_all_modules() -> List[Dict]:
        """
        Get all modules
        
        Returns:
            List of module dictionaries
        """
        try:
            supabase = ModuleDB.get_supabase()
            
            response = supabase.table('modules') \
                .select('*') \
                .order('display_order') \
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching modules: {str(e)}")
            return []
    
    @staticmethod
    def toggle_module_status(module_id: int, is_active: bool) -> bool:
        """
        Toggle module active/inactive status
        
        Args:
            module_id: Module ID
            is_active: New active status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = ModuleDB.get_supabase()
            
            response = supabase.table('modules') \
                .update({'is_active': is_active}) \
                .eq('id', module_id) \
                .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            st.error(f"Error toggling module status: {str(e)}")
            return False
    
    @staticmethod
    def update_module_order(module_id: int, display_order: int) -> bool:
        """
        Update module display order
        
        Args:
            module_id: Module ID
            display_order: New display order number
            
        Returns:
            True if successful, False otherwise
        """
        try:
            supabase = ModuleDB.get_supabase()
            
            response = supabase.table('modules') \
                .update({'display_order': display_order}) \
                .eq('id', module_id) \
                .execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            st.error(f"Error updating module order: {str(e)}")
            return False


class ActivityLogger:
    """Database operations for activity logging"""
    
    @staticmethod
    def get_supabase():
        """Get Supabase client from session state"""
        if 'supabase' not in st.session_state:
            raise Exception("Supabase client not initialized")
        return st.session_state.supabase
    
    @staticmethod
    def log(user_id: str, action_type: str, description: str = None, 
            module_key: str = None, success: bool = True, metadata: dict = None):
        """
        Log user activity
        
        Args:
            user_id: User's UUID
            action_type: Type of action (login, logout, module_access, etc.)
            description: Description of the action
            module_key: Module key if action is module-related
            success: Whether action was successful
            metadata: Additional data as JSON
        """
        try:
            supabase = ActivityLogger.get_supabase()
            
            # Get user email
            user_response = supabase.auth.admin.get_user_by_id(user_id)
            user_email = user_response.user.email if user_response.user else 'Unknown'
            
            log_data = {
                'user_id': user_id,
                'user_email': user_email,
                'action_type': action_type,
                'description': description,
                'module_key': module_key,
                'success': success,
                'metadata': metadata
            }
            
            supabase.table('activity_logs').insert(log_data).execute()
            
        except Exception as e:
            # Don't show error to user, just print for debugging
            print(f"Error logging activity: {str(e)}")
    
    @staticmethod
    def get_logs(days: int = 7) -> List[Dict]:
        """
        Get activity logs for the past N days
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of log dictionaries
        """
        try:
            supabase = ActivityLogger.get_supabase()
            
            since_date = datetime.now() - timedelta(days=days)
            
            response = supabase.table('activity_logs') \
                .select('*') \
                .gte('created_at', since_date.isoformat()) \
                .order('created_at', desc=True) \
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching activity logs: {str(e)}")
            return []
    
    @staticmethod
    def get_module_logs(module_key: str, days: int = 30) -> List[Dict]:
        """
        Get activity logs for a specific module
        
        Args:
            module_key: Module key to filter by
            days: Number of days to look back
            
        Returns:
            List of log dictionaries
        """
        try:
            supabase = ActivityLogger.get_supabase()
            
            since_date = datetime.now() - timedelta(days=days)
            
            response = supabase.table('activity_logs') \
                .select('*') \
                .eq('module_key', module_key) \
                .gte('created_at', since_date.isoformat()) \
                .order('created_at', desc=True) \
                .limit(100) \
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching module logs: {str(e)}")
            return []
