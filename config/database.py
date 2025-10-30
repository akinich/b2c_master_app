"""
Database configuration and connection utilities for Supabase
UPDATED FOR HYBRID PERMISSION SYSTEM (Admin + User with module-level permissions)
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
        """Get all modules accessible to a user (hybrid permission check)"""
        try:
            db = Database.get_client()
            # Use the new view that handles hybrid permissions
            response = (db.table('user_accessible_modules')
                       .select('*')
                       .eq('user_id', user_id)
                       .order('display_order')
                       .execute())
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
    def get_non_admin_users() -> List[Dict]:
        """Get all non-admin users (for permission management)"""
        try:
            db = Database.get_client()
            response = (db.table('user_details')
                       .select('*')
                       .neq('role_name', 'Admin')
                       .eq('is_active', True)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching non-admin users: {str(e)}")
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
        """Get all available roles (should only be Admin and User now)"""
        try:
            db = Database.get_client()
            response = (db.table('roles')
                       .select('*')
                       .in_('role_name', ['Admin', 'User'])
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching roles: {str(e)}")
            return []
    
    @staticmethod
    def get_role_permissions(role_id: int) -> List[Dict]:
        """Get all module permissions for a role (Admin only now)"""
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
        """Update permission for a role-module combination (Admin only)"""
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


class UserPermissionDB:
    """User-specific module permission operations (NEW FOR HYBRID SYSTEM)"""
    
    @staticmethod
    def get_user_permissions(user_id: str) -> List[Dict]:
        """Get all module permissions for a specific user"""
        try:
            db = Database.get_client()
            response = (db.table('user_module_permissions')
                       .select('*, modules(*)')
                       .eq('user_id', user_id)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching user permissions: {str(e)}")
            return []
    
    @staticmethod
    def get_user_permissions_detail(user_id: str) -> List[Dict]:
        """Get detailed permission info for a user (includes all modules)"""
        try:
            db = Database.get_client()
            response = (db.table('user_permissions_detail')
                       .select('*')
                       .eq('user_id', user_id)
                       .order('display_order')
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching user permissions detail: {str(e)}")
            return []
    
    @staticmethod
    def update_user_permission(user_id: str, module_id: int, can_access: bool, 
                              granted_by: str) -> bool:
        """Grant or revoke module access for a user"""
        try:
            db = Database.get_client()
            
            if can_access:
                # Grant access - upsert
                data = {
                    'user_id': user_id,
                    'module_id': module_id,
                    'can_access': True,
                    'granted_by': granted_by
                }
                db.table('user_module_permissions').upsert(
                    data,
                    on_conflict='user_id,module_id'
                ).execute()
            else:
                # Revoke access - delete the permission row
                db.table('user_module_permissions').delete().match({
                    'user_id': user_id,
                    'module_id': module_id
                }).execute()
            
            return True
        except Exception as e:
            st.error(f"Error updating user permission: {str(e)}")
            return False
    
    @staticmethod
    def bulk_update_user_permissions(user_id: str, module_ids: List[int], 
                                    granted_by: str) -> bool:
        """Set all permissions for a user at once (replaces existing)"""
        try:
            db = Database.get_client()
            
            # Delete all existing permissions for this user
            db.table('user_module_permissions').delete().eq('user_id', user_id).execute()
            
            # Insert new permissions
            if module_ids:
                permissions = [
                    {
                        'user_id': user_id,
                        'module_id': module_id,
                        'can_access': True,
                        'granted_by': granted_by
                    }
                    for module_id in module_ids
                ]
                db.table('user_module_permissions').insert(permissions).execute()
            
            return True
        except Exception as e:
            st.error(f"Error bulk updating user permissions: {str(e)}")
            return False
    
    @staticmethod
    def get_all_user_permissions() -> List[Dict]:
        """Get permissions for all users (admin panel overview)"""
        try:
            db = Database.get_client()
            response = (db.table('user_permissions_detail')
                       .select('*')
                       .order('email', 'display_order')
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching all user permissions: {str(e)}")
            return []
    
    @staticmethod
    def has_module_access(user_id: str, module_key: str) -> bool:
        """Check if a specific user has access to a specific module"""
        try:
            db = Database.get_client()
            
            # Check if user is admin
            user_profile = UserDB.get_user_profile(user_id)
            if user_profile and user_profile.get('role_name') == 'Admin':
                return True
            
            # Check user_accessible_modules view
            response = (db.table('user_accessible_modules')
                       .select('module_key')
                       .eq('user_id', user_id)
                       .eq('module_key', module_key)
                       .execute())
            
            return len(response.data) > 0 if response.data else False
        except Exception as e:
            st.error(f"Error checking module access: {str(e)}")
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
    def get_active_modules() -> List[Dict]:
        """Get all active modules"""
        try:
            db = Database.get_client()
            response = (db.table('modules')
                       .select('*')
                       .eq('is_active', True)
                       .order('display_order')
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching active modules: {str(e)}")
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


class WooCommerceDB:
    """WooCommerce product tracking database operations"""
    
    @staticmethod
    def get_all_products() -> List[Dict]:
        """Get all WooCommerce products from database"""
        try:
            db = Database.get_client()
            response = db.table('woocommerce_products').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching WooCommerce products: {str(e)}")
            return []
    
    @staticmethod
    def add_product(product_id: int, product_name: str = None, product_type: str = 'simple',
                   parent_id: int = None, sku: str = None, created_by: str = None) -> bool:
        """Add or update product in tracking"""
        try:
            db = Database.get_client()
            db.rpc('add_woocommerce_product', {
                'p_product_id': product_id,
                'p_product_name': product_name,
                'p_product_type': product_type,
                'p_parent_id': parent_id,
                'p_sku': sku,
                'p_created_by': created_by
            }).execute()
            return True
        except Exception as e:
            st.error(f"Error adding product: {str(e)}")
            return False
    
    @staticmethod
    def bulk_add_products(products: List[Dict]) -> int:
        """Add multiple products at once"""
        try:
            db = Database.get_client()
            data = []
            for p in products:
                data.append({
                    'product_id': p['product_id'],
                    'product_name': p.get('product_name'),
                    'product_type': p.get('product_type', 'simple'),
                    'parent_id': p.get('parent_id'),
                    'sku': p.get('sku'),
                    'created_by': p.get('created_by')
                })
            
            response = db.table('woocommerce_products').upsert(
                data,
                on_conflict='product_id'
            ).execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            st.error(f"Error bulk adding products: {str(e)}")
            return 0
    
    @staticmethod
    def deactivate_product(product_id: int) -> bool:
        """Mark product as inactive"""
        try:
            db = Database.get_client()
            db.table('woocommerce_products').update({
                'is_active': False
            }).eq('product_id', product_id).execute()
            return True
        except Exception as e:
            st.error(f"Error deactivating product: {str(e)}")
            return False
    
    @staticmethod
    def activate_product(product_id: int) -> bool:
        """Mark product as active"""
        try:
            db = Database.get_client()
            db.table('woocommerce_products').update({
                'is_active': True
            }).eq('product_id', product_id).execute()
            return True
        except Exception as e:
            st.error(f"Error activating product: {str(e)}")
            return False
    
    @staticmethod
    def log_update(product_id: int, parent_id: int, product_name: str, update_type: str,
                  old_regular: float = None, old_sale: float = None, old_stock: int = None,
                  new_regular: float = None, new_sale: float = None, new_stock: int = None,
                  success: bool = True, error_msg: str = None, api_code: int = None,
                  updated_by: str = None) -> bool:
        """Log price/stock update"""
        try:
            db = Database.get_client()
            db.rpc('log_woocommerce_update', {
                'p_product_id': product_id,
                'p_parent_id': parent_id,
                'p_product_name': product_name,
                'p_update_type': update_type,
                'p_old_regular_price': old_regular,
                'p_old_sale_price': old_sale,
                'p_old_stock': old_stock,
                'p_new_regular_price': new_regular,
                'p_new_sale_price': new_sale,
                'p_new_stock': new_stock,
                'p_success': success,
                'p_error_message': error_msg,
                'p_api_code': api_code,
                'p_updated_by': updated_by
            }).execute()
            return True
        except Exception as e:
            print(f"Error logging update: {str(e)}")
            return False
    
    @staticmethod
    def get_update_history(limit: int = 100) -> List[Dict]:
        """Get recent update history"""
        try:
            db = Database.get_client()
            response = (db.from_('woocommerce_recent_updates')
                       .select('*')
                       .limit(limit)
                       .execute())
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Error fetching update history: {str(e)}")
            return []
    
    @staticmethod
    def get_validation_rules() -> Dict:
        """Get validation rules as dictionary"""
        try:
            db = Database.get_client()
            response = (db.table('woocommerce_validation_rules')
                       .select('*')
                       .eq('is_active', True)
                       .execute())
            
            if response.data:
                rules = {}
                for rule in response.data:
                    rules[rule['rule_type']] = float(rule['rule_value'])
                return rules
            return {
                'price_min': 0.01,
                'price_max': 100000.00,
                'stock_min': 0,
                'stock_max': 10000
            }
        except Exception as e:
            st.error(f"Error fetching validation rules: {str(e)}")
            return {
                'price_min': 0.01,
                'price_max': 100000.00,
                'stock_min': 0,
                'stock_max': 10000
            }


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
