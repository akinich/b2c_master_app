"""
Database configuration and connection utilities for Supabase
"""
import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, List, Any
import json

class Database:
    """Handles all database operations with Supabase"""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client (singleton pattern)"""
        if cls._instance is None:
            try:
                url = st.secrets["supabase"]["url"]
                key = st.secrets["supabase"]["service_role_key"]
                cls._instance = create_client(url, key)
            except Exception as e:
                st.error(f"Failed to connect to database: {str(e)}")
                st.stop()
        return cls._instance
    
    @classmethod
    def reset_client(cls):
        """Reset the client (useful for testing or reconnecting)"""
        cls._instance = None


class UserDB:
    """User-related database operations"""
    
    @staticmethod
    def get_user_profile(user_id: str) -> Optional[Dict]:
        """Get user profile with role information"""
        try:
            db = Database.get_client()
            response = db.table('user_details').select('*').eq('id', user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Error fetching user profile: {str(e)}")
            return None
    
    @staticmethod
    def get_user_modules(user_id: str) -> List[Dict]:
        """Get all modules accessible to a user"""
        try:
            db = Database.get_client()
            response = db.rpc('get_user_modules', {'p_user_id': user_id}).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching user modules: {str(e)}")
            return []
    
    @staticmethod
    def create_user_profile(user_id: str, email: str, full_name: str, role_id: int) -> bool:
        """Create a new user profile after Supabase auth registration"""
        try:
            db = Database.get_client()
            data = {
                'id': user_id,
                'full_name': full_name,
                'role_id': role_id,
                'is_active': True
            }
            db.table('user_profiles').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error creating user profile: {str(e)}")
            return False
    
    @staticmethod
    def update_user_profile(user_id: str, updates: Dict) -> bool:
        """Update user profile information"""
        try:
            db = Database.get_client()
            db.table('user_profiles').update(updates).eq('id', user_id).execute()
            return True
        except Exception as e:
            st.error(f"Error updating user profile: {str(e)}")
            return False
    
    @staticmethod
    def get_all_users() -> List[Dict]:
        """Get all users with their profiles (for admin panel)"""
        try:
            db = Database.get_client()
            response = db.table('user_details').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching all users: {str(e)}")
            return []
    
    @staticmethod
    def deactivate_user(user_id: str) -> bool:
        """Deactivate a user account"""
        return UserDB.update_user_profile(user_id, {'is_active': False})
    
    @staticmethod
    def activate_user(user_id: str) -> bool:
        """Activate a user account"""
        return UserDB.update_user_profile(user_id, {'is_active': True})


class RoleDB:
    """Role and permission related database operations"""
    
    @staticmethod
    def get_all_roles() -> List[Dict]:
        """Get all available roles"""
        try:
            db = Database.get_client()
            response = db.table('roles').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching roles: {str(e)}")
            return []
    
    @staticmethod
    def get_role_permissions(role_id: int) -> List[Dict]:
        """Get all module permissions for a role"""
        try:
            db = Database.get_client()
            response = (db.table('role_permissions')
                       .select('*, modules(*)')
                       .eq('role_id', role_id)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching role permissions: {str(e)}")
            return []
    
    @staticmethod
    def update_role_permission(role_id: int, module_id: int, can_access: bool) -> bool:
        """Update permission for a role-module combination"""
        try:
            db = Database.get_client()
            # Try to update first
            response = (db.table('role_permissions')
                       .update({'can_access': can_access})
                       .eq('role_id', role_id)
                       .eq('module_id', module_id)
                       .execute())
            
            # If no rows affected, insert new permission
            if not response.data:
                db.table('role_permissions').insert({
                    'role_id': role_id,
                    'module_id': module_id,
                    'can_access': can_access
                }).execute()
            
            return True
        except Exception as e:
            st.error(f"Error updating role permission: {str(e)}")
            return False


class ModuleDB:
    """Module related database operations"""
    
    @staticmethod
    def get_all_modules() -> List[Dict]:
        """Get all available modules"""
        try:
            db = Database.get_client()
            response = (db.table('modules')
                       .select('*')
                       .order('display_order')
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching modules: {str(e)}")
            return []
    
    @staticmethod
    def add_module(module_name: str, module_key: str, description: str, 
                   icon: str = '⚙️', display_order: int = 99) -> bool:
        """Add a new module to the system"""
        try:
            db = Database.get_client()
            data = {
                'module_name': module_name,
                'module_key': module_key,
                'description': description,
                'icon': icon,
                'display_order': display_order,
                'is_active': True
            }
            db.table('modules').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Error adding module: {str(e)}")
            return False
    
    @staticmethod
    def update_module(module_id: int, updates: Dict) -> bool:
        """Update module information"""
        try:
            db = Database.get_client()
            db.table('modules').update(updates).eq('id', module_id).execute()
            return True
        except Exception as e:
            st.error(f"Error updating module: {str(e)}")
            return False
    
    @staticmethod
    def toggle_module_status(module_id: int, is_active: bool) -> bool:
        """Activate or deactivate a module"""
        return ModuleDB.update_module(module_id, {'is_active': is_active})


class ActivityLogger:
    """Activity logging database operations"""
    
    @staticmethod
    def log(user_id: str, action_type: str, module_key: str = None, 
            description: str = None, metadata: Dict = None, success: bool = True) -> bool:
        """Log user activity"""
        try:
            db = Database.get_client()
            db.rpc('log_activity', {
                'p_user_id': user_id,
                'p_action_type': action_type,
                'p_module_key': module_key,
                'p_description': description,
                'p_metadata': json.dumps(metadata) if metadata else None
            }).execute()
            return True
        except Exception as e:
            # Don't show error to user for logging failures
            print(f"Error logging activity: {str(e)}")
            return False
    
    @staticmethod
    def get_user_activity(user_id: str, limit: int = 50) -> List[Dict]:
        """Get recent activity for a specific user"""
        try:
            db = Database.get_client()
            response = (db.table('activity_logs')
                       .select('*')
                       .eq('user_id', user_id)
                       .order('created_at', desc=True)
                       .limit(limit)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching activity logs: {str(e)}")
            return []
    
    @staticmethod
    def get_all_activity(limit: int = 100) -> List[Dict]:
        """Get recent activity for all users (admin only)"""
        try:
            db = Database.get_client()
            response = (db.table('activity_logs')
                       .select('*')
                       .order('created_at', desc=True)
                       .limit(limit)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching activity logs: {str(e)}")
            return []
    
    @staticmethod
    def get_module_activity(module_key: str, limit: int = 50) -> List[Dict]:
        """Get recent activity for a specific module"""
        try:
            db = Database.get_client()
            response = (db.table('activity_logs')
                       .select('*')
                       .eq('module_key', module_key)
                       .order('created_at', desc=True)
                       .limit(limit)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching module activity: {str(e)}")
            return []
