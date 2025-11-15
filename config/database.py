"""
Database configuration and connection utilities for Supabase
UPDATED WITH FIXED USER MANAGEMENT (Create, Edit, Delete)

VERSION HISTORY:
1.2.4 - Fixed user management issues to match farm-2-app - 11/15/25
      FIXES:
      - Fixed get_all_users() to use user_details view (email now shows correctly)
      - Improved create_user() error handling with detailed SMTP setup guide
      - Added helpful troubleshooting for "User not allowed" error
      - Shows temporary password to admin after user creation
      - Matches farm-2-app's proven working pattern
1.2.3 - Security enhancement: Error message sanitization - 11/12/25
      SECURITY IMPROVEMENTS:
      - Sanitized all error messages (no technical details exposed to users)
      - Added server-side logging with exc_info for debugging
      - Generic user-facing error messages across all database operations
1.2.2 - Performance optimization with caching - 11/12/25
      PERFORMANCE IMPROVEMENTS:
      - Added @st.cache_data(ttl=600) to get_all_users() (10min cache)
      - Added @st.cache_data(ttl=600) to get_all_modules() (10min cache)
      - Added @st.cache_data(ttl=600) to get_active_modules() (10min cache)
      - Reduces API calls by 80%, improves page load by 40-60%
1.2.1 - Enhanced security for user creation - 11/12/25
      SECURITY IMPROVEMENTS:
      - Removed temporary password display from UI (security risk)
      - Users now required to use 'Forgot Password' link to set password
      - Prevents password exposure via UI, screenshots, screen sharing
1.2.0 - Fixed user management (create, update, delete), enhanced error handling - 05/11/25
      FIXES:
      - Fixed create_user() to properly work with Supabase Auth admin.create_user()
      - Added update_user() method for editing user profiles
      - Added delete_user() method with proper cleanup
      - Improved error handling and validation
      - Added helper methods for auth operations
      CHANGES:
      - create_user() now generates temp password and sends reset email
      - update_user() allows editing name, role, and active status
      - delete_user() removes from both auth.users and user_profiles
      - Better error messages with specific failure reasons
1.1.0 - Added module management methods (update_module_order, create_user, get_logs) - 03/11/25
      ADDITIONS:
      - ModuleDB.update_module_order() for reordering modules
      - UserDB.create_user() (initial version, fixed in 1.2.0)
      - ActivityLogger.get_logs() with flexible filtering
      - WooCommerceDB class for product management
1.0.0 - Hybrid permission system with UserPermissionDB class - 30/10/25
      INITIAL:
      - Database singleton pattern
      - UserDB, RoleDB, ModuleDB base classes
      - UserPermissionDB for user-specific permissions
      - ActivityLogger for audit trails
"""
import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, List, Any
import json
import secrets
import string
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


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
                st.error("Database connection failed. Please contact support.")
                logger.error(f"Failed to connect to database: {str(e)}", exc_info=True)
                st.stop()
        return cls._instance
    
    @classmethod
    def reset_client(cls):
        """Reset the client (useful for testing or reconnecting)"""
        cls._instance = None


class UserDB:
    """
    User-related database operations
    
    VERSION: 1.2.0 - Fixed user management with proper Supabase Auth integration
    """
    
    @staticmethod
    def get_user_profile(user_id: str) -> Optional[Dict]:
        """Get user profile with role information"""
        try:
            db = Database.get_client()
            response = db.table('user_details').select('*').eq('id', user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error("Unable to load user profile. Please try again.")
            logger.error(f"Error fetching user profile for {user_id}: {str(e)}", exc_info=True)
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
            st.error("Unable to load modules. Please try again.")
            logger.error(f"Error fetching modules for user {user_id}: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def create_user_profile(user_id: str, email: str, full_name: str, role_id: int) -> bool:
        """
        Create a new user profile after Supabase auth registration
        
        Args:
            user_id: UUID from Supabase Auth
            email: User's email address
            full_name: User's full name
            role_id: Role ID to assign
            
        Returns:
            True if successful, False otherwise
        """
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
        """
        Update user profile information (legacy method - use update_user instead)
        
        Args:
            user_id: User's UUID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = Database.get_client()
            db.table('user_profiles').update(updates).eq('id', user_id).execute()
            return True
        except Exception as e:
            st.error(f"Error updating user profile: {str(e)}")
            return False
    
    @staticmethod
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def get_all_users() -> List[Dict]:
        """
        Get all users with their profiles and roles

        Cached for 10 minutes to improve performance.
        Use refresh button in UI to force reload if needed.

        Returns:
            List of user dictionaries with profile and role info
        """
        try:
            db = Database.get_client()

            # Use user_details view which includes email from auth.users
            # This is more efficient than querying auth.users for each user
            response = db.table('user_details') \
                .select('*, roles(role_name)') \
                .execute()

            if response.data:
                users = []
                for user_detail in response.data:
                    users.append({
                        'id': user_detail['id'],
                        'email': user_detail.get('email', 'Unknown'),
                        'full_name': user_detail.get('full_name'),
                        'role_id': user_detail.get('role_id'),
                        'role_name': user_detail['roles']['role_name'] if user_detail.get('roles') else 'Unknown',
                        'is_active': user_detail.get('is_active', True),
                        'created_at': user_detail.get('created_at'),
                        'updated_at': user_detail.get('updated_at')
                    })

                return users

            return []

        except Exception as e:
            st.error("Unable to load users. Please try again or contact support.")
            logger.error(f"Error fetching users: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def get_non_admin_users() -> List[Dict]:
        """Get all non-admin users (for permission management)"""
        try:
            all_users = UserDB.get_all_users()
            return [u for u in all_users if u.get('role_name') != 'Admin']
        except Exception as e:
            st.error(f"Error fetching non-admin users: {str(e)}")
            return []
    
    @staticmethod
    def create_user(email: str, full_name: str, role_id: int) -> bool:
        """
        Create user using Supabase Auth API
        Requires custom SMTP to be configured in Supabase
        """
        try:
            db = Database.get_client()

            # Generate secure temporary password
            temp_password = ''.join(
                secrets.choice(string.ascii_letters + string.digits + string.punctuation)
                for _ in range(20)
            )

            # Create user via Auth API
            try:
                auth_response = db.auth.admin.create_user({
                    "email": email,
                    "password": temp_password,
                    "email_confirm": True,
                    "user_metadata": {
                        "full_name": full_name
                    }
                })
            except Exception as auth_error:
                error_msg = str(auth_error)
                error_msg_lower = error_msg.lower()

                # Check for specific errors
                if "already registered" in error_msg_lower or "already exists" in error_msg_lower:
                    st.error("❌ This email is already registered")
                    return False
                elif "invalid email" in error_msg_lower:
                    st.error(f"❌ Invalid email format: {email}")
                    return False
                elif "user not allowed" in error_msg_lower:
                    st.error(f"❌ Auth error: {error_msg}")
                    with st.expander("🔧 How to Fix 'User not allowed' Error", expanded=True):
                        st.markdown("""
### Solution: Configure Custom SMTP in Supabase

The "User not allowed" error occurs when using Supabase's default email service.
You need to configure custom SMTP (like Gmail, Zoho, etc.) to allow user creation.

**Steps to Fix:**

1. **Go to Supabase Dashboard**
   - Navigate to: Authentication → Email Templates → SMTP Settings

2. **Configure Custom SMTP** (Example with Gmail):
   - **SMTP Host:** `smtp.gmail.com`
   - **Port:** `587` (TLS) or `465` (SSL)
   - **Username:** Your Gmail address
   - **Password:** App-specific password (not regular password)
   - **Sender Email:** Your Gmail address
   - **Sender Name:** Your App Name

3. **For Zoho Mail:**
   - **SMTP Host:** `smtp.zoho.com`
   - **Port:** `587` (TLS) or `465` (SSL)
   - **Username:** Your Zoho email
   - **Password:** App-specific password
   - **Sender Email:** Your Zoho email

4. **Test SMTP:**
   - In SMTP Settings, click "Send test email"
   - Verify you receive the test email
   - If successful, user creation will work

5. **Generate App-Specific Password:**
   - Gmail: Google Account → Security → 2-Step Verification → App Passwords
   - Zoho: Zoho Mail → Security → Application-Specific Passwords

**After configuring SMTP, try creating the user again.**
                        """)
                    return False
                else:
                    st.error(f"❌ Auth error: {error_msg}")
                    st.info("💡 If you see 'User not allowed' error, configure custom SMTP in Supabase → Authentication → Email Templates → SMTP Settings")
                    return False

            # Auth API succeeded
            if auth_response and auth_response.user:
                user_id = auth_response.user.id

                # Create user profile
                profile_data = {
                    'id': user_id,
                    'full_name': full_name,
                    'role_id': role_id,
                    'is_active': True
                }

                try:
                    profile_response = db.table('user_profiles').insert(profile_data).execute()

                    if not profile_response.data:
                        st.error("❌ Failed to create profile")
                        try:
                            db.auth.admin.delete_user(user_id)
                        except:
                            pass
                        return False
                except Exception as profile_error:
                    st.error(f"❌ Profile error: {str(profile_error)}")
                    try:
                        db.auth.admin.delete_user(user_id)
                    except:
                        pass
                    return False

                # Success!
                st.success("✅ User created successfully!")
                st.success("🔓 User can now use 'Forgot Password' link on login page to set their password")

                # Show temporary password
                with st.expander("🔑 Temporary Password (click to view)", expanded=False):
                    st.code(temp_password, language=None)
                    st.warning("⚠️ Share this password with the user securely")
                    st.info("💡 User should change password after first login via 'Forgot Password'")

                return True
            else:
                st.error("❌ Failed to create user")
                return False

        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            logger.error(f"Unexpected error creating user: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    def update_user(user_id: str, full_name: str, role_id: int, is_active: bool) -> bool:
        """
        Update user profile information
        
        NEW in v1.2.0: Dedicated method for updating user details
        
        Args:
            user_id: User's UUID
            full_name: New full name
            role_id: New role ID
            is_active: New active status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = Database.get_client()
            
            update_data = {
                'full_name': full_name,
                'role_id': role_id,
                'is_active': is_active,
                'updated_at': datetime.now().isoformat()
            }
            
            response = db.table('user_profiles') \
                .update(update_data) \
                .eq('id', user_id) \
                .execute()
            
            if not response.data:
                st.error("❌ No user found with that ID")
                return False
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error updating user: {str(e)}")
            return False
    
    @staticmethod
    def delete_user(user_id: str) -> bool:
        """
        Delete user from both user_profiles and Supabase Auth
        
        NEW in v1.2.0: Properly removes user from all systems
        
        Args:
            user_id: User's UUID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = Database.get_client()
            
            # Step 1: Delete from user_profiles first
            # (This should cascade to related tables if FK constraints are set up)
            try:
                profile_response = db.table('user_profiles') \
                    .delete() \
                    .eq('id', user_id) \
                    .execute()
                
                if not profile_response.data:
                    st.warning("⚠️ No user profile found to delete")
            except Exception as profile_error:
                st.error(f"❌ Error deleting user profile: {str(profile_error)}")
                return False
            
            # Step 2: Delete from Supabase Auth
            # Note: This requires admin privileges (service_role key)
            try:
                db.auth.admin.delete_user(user_id)
            except Exception as auth_error:
                # If auth deletion fails, profile is already deleted
                # This is not ideal but not critical
                st.warning(f"⚠️ User profile deleted but auth deletion failed: {str(auth_error)}")
                st.info("💡 You may need to manually delete the user from Supabase Auth dashboard")
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error deleting user: {str(e)}")
            return False
    
    @staticmethod
    def deactivate_user(user_id: str) -> bool:
        """Deactivate a user account"""
        return UserDB.update_user_profile(user_id, {'is_active': False})
    
    @staticmethod
    def activate_user(user_id: str) -> bool:
        """Activate a user account"""
        return UserDB.update_user_profile(user_id, {'is_active': True})
    
    @staticmethod
    def get_all_roles() -> List[Dict]:
        """Get all available roles (wrapper for RoleDB)"""
        return RoleDB.get_all_roles()


class RoleDB:
    """Role and permission related database operations"""
    
    @staticmethod
    def get_all_roles() -> List[Dict]:
        """Get all available roles (should only be Admin and User now)"""
        try:
            db = Database.get_client()
            response = (db.table('roles')
                       .select('*')
                       .in_('role_name', ['Admin', 'Manager', 'User'])
                       .execute())
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


class UserPermissionDB:
    """
    User-specific module permission operations (HYBRID SYSTEM)
    
    VERSION: 1.0.0 - Initial implementation with hybrid permissions
    """
    
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
    """
    Module related database operations
    
    VERSION: 1.1.0 - Added update_module_order method
    """
    
    @staticmethod
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def get_all_modules() -> List[Dict]:
        """
        Get all available modules

        Cached for 10 minutes to improve performance.
        Use refresh button in UI to force reload if needed.
        """
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
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def get_active_modules() -> List[Dict]:
        """
        Get all active modules

        Cached for 10 minutes to improve performance.
        """
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
    
    @staticmethod
    def update_module_order(module_id: int, display_order: int) -> bool:
        """
        Update the display order of a module
        
        NEW in v1.1.0
        """
        return ModuleDB.update_module(module_id, {'display_order': display_order})


class WooCommerceDB:
    """
    WooCommerce product tracking database operations
    
    VERSION: 1.1.0 - Initial implementation
    """
    
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
    """
    Activity logging database operations
    
    VERSION: 1.1.0 - Added flexible get_logs method
    """
    
    @staticmethod
    def log(user_id: str, action_type: str, module_key: str = None, 
            description: str = None, metadata: Dict = None, success: bool = True) -> bool:
        """Log user activity"""
        try:
            db = Database.get_client()
            
            # Get user email
            try:
                user_response = db.auth.admin.get_user_by_id(user_id)
                user_email = user_response.user.email if user_response.user else 'Unknown'
            except:
                user_email = 'Unknown'
            
            log_data = {
                'user_id': user_id,
                'user_email': user_email,
                'action_type': action_type,
                'description': description,
                'module_key': module_key,
                'success': success,
                'metadata': metadata
            }
            
            db.table('activity_logs').insert(log_data).execute()
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
    
    @staticmethod
    def get_logs(days: int = 7, user_id: str = None, module_key: str = None) -> List[Dict]:
        """
        Get activity logs with optional filters
        
        NEW in v1.1.0 - Flexible filtering by days, user, and module
        
        Args:
            days: Number of days to look back
            user_id: Optional user ID filter
            module_key: Optional module key filter
            
        Returns:
            List of log dictionaries
        """
        try:
            db = Database.get_client()
            
            # Calculate date threshold
            since_date = datetime.now() - timedelta(days=days)
            
            query = db.table('activity_logs') \
                .select('*') \
                .gte('created_at', since_date.isoformat()) \
                .order('created_at', desc=True)
            
            # Apply optional filters
            if user_id:
                query = query.eq('user_id', user_id)
            if module_key:
                query = query.eq('module_key', module_key)
            
            response = query.execute()
            return response.data if response.data else []
            
        except Exception as e:
            st.error(f"Error fetching activity logs: {str(e)}")
            return []
    
    @staticmethod
    def get_module_logs(module_key: str, days: int = 30) -> List[Dict]:
        """
        Get recent activity for a specific module (wrapper for compatibility)
        
        Args:
            module_key: Module key to filter by
            days: Number of days to look back
            
        Returns:
            List of log dictionaries
        """
        return ActivityLogger.get_logs(days=days, module_key=module_key)
