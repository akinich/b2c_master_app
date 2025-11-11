"""
Admin Panel Components - FIXED VERSION
Handles user management, permissions, activity logs, and module management

VERSION: 1.2.0
DATE: 11/05/25
FIXES:
- Fixed user creation to properly work with Supabase Auth
- Added user deletion with confirmation
- Added user editing (name, role, status)
- Improved error handling and validation
- Better UI/UX with status indicators
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import re
from typing import List, Dict, Optional
from auth.session import SessionManager
from config.database import UserDB, ModuleDB, ActivityLogger, UserPermissionDB


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def show_user_status_badge(is_active: bool):
    """Display user status badge"""
    if is_active:
        st.markdown("🟢 **Active**")
    else:
        st.markdown("🔴 **Inactive**")


# =====================================================
# USER MANAGEMENT
# =====================================================

def show_user_management():
    """Admin panel for managing users"""
    SessionManager.require_admin()
    
    st.markdown("### 👥 User Management")
    st.markdown("Manage user accounts and access")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📋 All Users", "➕ Add New User", "✏️ Edit User"])
    
    with tab1:
        show_all_users()
    
    with tab2:
        show_add_user_form()
    
    with tab3:
        show_edit_user()


def show_all_users():
    """Display all users in the system with enhanced controls"""
    st.markdown("#### All Users")
    
    users = UserDB.get_all_users()
    
    if users:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Users", len(users))
        with col2:
            active_count = sum(1 for u in users if u.get('is_active', True))
            st.metric("Active Users", active_count)
        with col3:
            admin_count = sum(1 for u in users if u.get('role_name') == 'Admin')
            st.metric("Admins", admin_count)
        with col4:
            manager_count = sum(1 for u in users if u.get('role_name') == 'Manager')
            st.metric("Managers", manager_count)
        
        st.markdown("---")
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "Active", "Inactive"])
        with col2:
            role_filter = st.selectbox("Filter by Role", ["All", "Admin", "Manager", "User"])
        
        # Apply filters
        filtered_users = users.copy()
        if status_filter != "All":
            filtered_users = [u for u in filtered_users if u.get('is_active', True) == (status_filter == "Active")]
        if role_filter != "All":
            filtered_users = [u for u in filtered_users if u.get('role_name') == role_filter]
        
        if filtered_users:
            # Create display dataframe
            df = pd.DataFrame(filtered_users)
            display_cols = ['email', 'full_name', 'role_name', 'is_active', 'created_at']
            
            # Ensure all columns exist
            for col in display_cols:
                if col not in df.columns:
                    df[col] = None
            
            df_display = df[display_cols].copy()
            df_display.columns = ['Email', 'Name', 'Role', 'Status', 'Created']
            df_display['Status'] = df_display['Status'].map({True: '✅ Active', False: '❌ Inactive', None: '❓ Unknown'})
            
            if 'Created' in df_display.columns and df_display['Created'].notna().any():
                df_display['Created'] = pd.to_datetime(df_display['Created'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            st.dataframe(df_display, width='stretch', hide_index=True)
            
            # Export option
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="📥 Download User List",
                data=csv,
                file_name=f"users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No users found matching the filters")
    else:
        st.warning("No users found in the system")


def show_add_user_form():
    """Form to add new user with improved validation"""
    st.markdown("#### Add New User")
    
    st.info("ℹ️ User will receive an email from Supabase to set their password. Make sure the email address is valid!")
    
    with st.form("add_user_form", clear_on_submit=True):
        # Email input with validation
        email = st.text_input(
            "Email Address *",
            placeholder="user@example.com",
            help="User will receive password setup email at this address"
        )
        
        # Full name input
        full_name = st.text_input(
            "Full Name *",
            placeholder="John Doe",
            help="User's full name as it will appear in the system"
        )
        
        # Role selection
        roles = UserDB.get_all_roles()
        if not roles:
            st.error("❌ No roles found in database. Please run the database setup script.")
            st.stop()
        
        role_options = {role['role_name']: role['id'] for role in roles}
        selected_role = st.selectbox(
            "Role *",
            options=list(role_options.keys()),
            help="User's access level"
        )
        
        # Display role description
        role_descriptions = {
            'Admin': '🔴 Full system access including user management',
            'Manager': '🟡 Access to most modules except user management',
            'User': '🟢 Limited access to basic modules'
        }
        if selected_role in role_descriptions:
            st.caption(role_descriptions[selected_role])
        
        st.markdown("---")
        
        # Submit button
        col1, col2 = st.columns([3, 1])
        with col2:
            submitted = st.form_submit_button("✅ Create User", type="primary", width='stretch')
        
        if submitted:
            # Validate inputs
            errors = []
            
            if not email:
                errors.append("Email is required")
            elif not validate_email(email):
                errors.append("Invalid email format")
            
            if not full_name or len(full_name.strip()) < 2:
                errors.append("Full name is required (minimum 2 characters)")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Create user
                with st.spinner("Creating user..."):
                    role_id = role_options[selected_role]
                    result = UserDB.create_user(email.strip().lower(), full_name.strip(), role_id)
                    
                    if result:
                        st.success(f"✅ User created successfully!")
                        st.success(f"📧 Verification email sent to {email}")
                        st.info("💡 The user must verify their email and set a password before they can login.")
                        
                        # Log admin action
                        admin_user = SessionManager.get_user()
                        ActivityLogger.log(
                            user_id=admin_user['id'],
                            action_type='admin_action',
                            description=f"Created new user: {email}",
                            metadata={
                                'email': email,
                                'role': selected_role,
                                'full_name': full_name
                            }
                        )
                        
                        # Show next steps
                        with st.expander("📋 Next Steps"):
                            st.markdown(f"""
                            1. ✅ User account created for **{email}**
                            2. 📧 Verification email sent to user
                            3. 🔐 User must check email and click verification link
                            4. 🔑 User will be prompted to set their password
                            5. 🚀 User can then login to the system
                            
                            **Note:** If user doesn't receive email:
                            - Check spam/junk folder
                            - Verify email address is correct
                            - You can resend verification from Supabase dashboard
                            """)
                        
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user. Possible reasons:")
                        st.error("• Email already exists in the system")
                        st.error("• Database connection issue")
                        st.error("• Invalid role configuration")
                        st.info("💡 Check the error logs or try a different email address")


def show_edit_user():
    """Edit existing user details"""
    st.markdown("#### Edit User")
    
    users = UserDB.get_all_users()
    
    if not users:
        st.warning("No users found")
        return
    
    # User selection
    user_options = {f"{u['email']} ({u.get('role_name', 'Unknown')})": u for u in users}
    selected_key = st.selectbox(
        "Select User to Edit",
        options=list(user_options.keys()),
        help="Choose a user to edit their details"
    )
    
    selected_user = user_options[selected_key]
    
    st.markdown("---")
    
    # Edit form
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Current Details:**")
        st.text(f"Email: {selected_user['email']}")
        st.text(f"Name: {selected_user.get('full_name', 'N/A')}")
        st.text(f"Role: {selected_user.get('role_name', 'N/A')}")
        current_status = selected_user.get('is_active', True)
        st.text(f"Status: {'Active' if current_status else 'Inactive'}")
    
    with col2:
        st.markdown("**Update Details:**")
        
        # New full name
        new_full_name = st.text_input(
            "Full Name",
            value=selected_user.get('full_name', ''),
            key="edit_full_name"
        )
        
        # New role
        roles = UserDB.get_all_roles()
        role_options = {role['role_name']: role['id'] for role in roles}
        current_role_name = selected_user.get('role_name', list(role_options.keys())[0])
        new_role = st.selectbox(
            "Role",
            options=list(role_options.keys()),
            index=list(role_options.keys()).index(current_role_name) if current_role_name in role_options else 0,
            key="edit_role"
        )
        
        # Active status
        new_status = st.checkbox(
            "Active",
            value=current_status,
            key="edit_status",
            help="Inactive users cannot login"
        )
    
    st.markdown("---")
    
    # Update and Delete buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("💾 Update User", type="primary", width='stretch'):
            # Check if any changes were made
            changes = []
            
            if new_full_name != selected_user.get('full_name', ''):
                changes.append(f"name: '{selected_user.get('full_name')}' → '{new_full_name}'")
            
            if role_options[new_role] != selected_user.get('role_id'):
                changes.append(f"role: '{current_role_name}' → '{new_role}'")
            
            if new_status != current_status:
                changes.append(f"status: '{'Active' if current_status else 'Inactive'}' → '{'Active' if new_status else 'Inactive'}'")
            
            if not changes:
                st.info("ℹ️ No changes detected")
            else:
                # Update user
                success = UserDB.update_user(
                    user_id=selected_user['id'],
                    full_name=new_full_name,
                    role_id=role_options[new_role],
                    is_active=new_status
                )
                
                if success:
                    st.success("✅ User updated successfully!")
                    
                    # Log admin action
                    admin_user = SessionManager.get_user()
                    ActivityLogger.log(
                        user_id=admin_user['id'],
                        action_type='admin_action',
                        description=f"Updated user: {selected_user['email']}",
                        metadata={
                            'target_user': selected_user['email'],
                            'changes': changes
                        }
                    )
                    
                    st.rerun()
                else:
                    st.error("❌ Failed to update user")
    
    with col3:
        if st.button("🗑️ Delete User", type="secondary", width='stretch'):
            st.session_state['confirm_delete_user'] = selected_user['id']
    
    # Delete confirmation
    if st.session_state.get('confirm_delete_user') == selected_user['id']:
        st.markdown("---")
        st.warning(f"⚠️ **Confirm Deletion**")
        st.error(f"Are you sure you want to delete user **{selected_user['email']}**?")
        st.error("This action cannot be undone!")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if st.button("✅ Yes, Delete", type="primary", width='stretch'):
                # Prevent deleting yourself
                admin_user = SessionManager.get_user()
                if selected_user['id'] == admin_user['id']:
                    st.error("❌ You cannot delete your own account!")
                    del st.session_state['confirm_delete_user']
                else:
                    # Delete user
                    success = UserDB.delete_user(selected_user['id'])
                    
                    if success:
                        st.success(f"✅ User {selected_user['email']} deleted successfully!")
                        
                        # Log admin action
                        ActivityLogger.log(
                            user_id=admin_user['id'],
                            action_type='admin_action',
                            description=f"Deleted user: {selected_user['email']}",
                            metadata={
                                'deleted_user': selected_user['email'],
                                'deleted_role': selected_user.get('role_name')
                            }
                        )
                        
                        del st.session_state['confirm_delete_user']
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete user")
        
        with col3:
            if st.button("❌ Cancel", width='stretch'):
                del st.session_state['confirm_delete_user']
                st.rerun()


# =====================================================
# USER PERMISSIONS
# =====================================================

def show_user_permissions():
    """Admin panel for managing user-specific module permissions"""
    SessionManager.require_admin()
    
    st.markdown("### 🔐 User Permissions")
    st.markdown("Configure module access for individual users")
    st.markdown("---")
    
    # Get all users and modules
    users = UserDB.get_all_users()
    modules = ModuleDB.get_all_modules()
    
    if not users or not modules:
        st.warning("No users or modules found")
        return
    
    # User selector
    user_options = {f"{user['email']} ({user['role_name']})": user for user in users}
    selected_user_key = st.selectbox("Select User", options=list(user_options.keys()))
    selected_user = user_options[selected_user_key]
    
    # User info card
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Email:** {selected_user['email']}")
    with col2:
        st.markdown(f"**Name:** {selected_user.get('full_name', 'N/A')}")
    with col3:
        st.markdown(f"**Role:** {selected_user.get('role_name', 'N/A')}")
    
    st.markdown("---")
    
    # Get user's current permissions
    user_permissions = UserPermissionDB.get_user_permissions(selected_user['id'])
    user_module_access = {perm['modules']['id']: perm['can_access'] for perm in user_permissions if 'modules' in perm}
    
    # Display modules with checkboxes
    st.markdown("#### Module Access")
    st.caption("Toggle module access for this specific user (overrides role-based permissions)")
    
    changes_made = False
    new_permissions = {}
    
    for module in modules:
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"{module['icon']} **{module['module_name']}**")
            st.caption(module.get('description', 'No description'))
        
        with col2:
            current_access = user_module_access.get(module['id'], False)
            new_access = st.checkbox(
                "Access",
                value=current_access,
                key=f"perm_{selected_user['id']}_{module['id']}"
            )
            new_permissions[module['id']] = new_access
            
            if new_access != current_access:
                changes_made = True
        
        with col3:
            if module.get('is_active'):
                st.markdown("✅ Active")
            else:
                st.markdown("❌ Inactive")
    
    # Save button
    st.markdown("---")
    if changes_made:
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("💾 Save Changes", type="primary", width='stretch'):
                success_count = 0
                admin_user = SessionManager.get_user()
                
                for module_id, new_access in new_permissions.items():
                    if UserPermissionDB.update_user_permission(
                        selected_user['id'], 
                        module_id, 
                        new_access,
                        admin_user['id']
                    ):
                        success_count += 1
                
                st.success(f"✅ Updated {success_count} permissions for {selected_user['email']}")
                
                # Log admin action
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Updated module permissions for {selected_user['email']}",
                    metadata={
                        'target_user': selected_user['email'],
                        'changes': success_count
                    }
                )
                
                st.rerun()
    else:
        st.info("ℹ️ No changes made. Toggle checkboxes above to modify permissions.")


# =====================================================
# ACTIVITY LOGS
# =====================================================

def show_activity_logs():
    """Admin panel for viewing activity logs with enhanced filtering"""
    SessionManager.require_admin()
    
    st.markdown("### 📊 Activity Logs")
    st.markdown("View user activity across all modules")
    st.markdown("---")
    
    # Filter controls
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        days_back = st.number_input("Days to show", min_value=1, max_value=90, value=7)
    
    with col2:
        users = UserDB.get_all_users()
        user_filter = st.selectbox("Filter by user", options=['All'] + [u['email'] for u in users])
    
    with col3:
        action_types = ['All', 'login', 'logout', 'module_access', 'admin_action', 'module_error', 'file_upload', 'pdf_generation']
        action_filter = st.selectbox("Filter by action", options=action_types)
    
    with col4:
        success_filter = st.selectbox("Filter by status", options=['All', 'Success', 'Failed'])
    
    # Fetch logs
    logs = ActivityLogger.get_logs(days=days_back)
    
    if logs:
        df = pd.DataFrame(logs)
        
        # Apply filters
        if user_filter != 'All':
            df = df[df['user_email'] == user_filter]
        
        if action_filter != 'All':
            df = df[df['action_type'] == action_filter]
        
        if success_filter != 'All':
            if success_filter == 'Success':
                df = df[df['success'] == True]
            else:
                df = df[df['success'] == False]
        
        if not df.empty:
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Logs", len(df))
            with col2:
                success_count = (df['success'] == True).sum()
                st.metric("Successful", success_count)
            with col3:
                failed_count = (df['success'] == False).sum()
                st.metric("Failed", failed_count)
            with col4:
                unique_users = df['user_email'].nunique()
                st.metric("Unique Users", unique_users)
            
            st.markdown("---")
            
            # Display logs
            display_df = df[['created_at', 'user_email', 'action_type', 'description', 'success']].copy()
            display_df.columns = ['Timestamp', 'User', 'Action', 'Description', 'Status']
            
            if 'Timestamp' in display_df.columns:
                display_df['Timestamp'] = pd.to_datetime(display_df['Timestamp'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            display_df['Status'] = display_df['Status'].map({
                True: '✅ Success',
                False: '❌ Failed',
                None: '➖ N/A'
            })
            
            st.dataframe(display_df, width='stretch', hide_index=True)
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"activity_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No logs found matching the filters")
    else:
        st.info("No activity logs found")


def show_module_logs(module_key: str):
    """Show activity logs for a specific module"""
    logs = ActivityLogger.get_module_logs(module_key=module_key, days=30)
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[['created_at', 'user_email', 'action_type', 'description']]
        df.columns = ['Timestamp', 'User', 'Action', 'Description']
        
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
        
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info(f"No activity logs found for this module")


# =====================================================
# MODULE MANAGEMENT
# =====================================================

def show_module_management():
    """Admin panel for managing modules - viewing, toggling, and reordering"""
    SessionManager.require_admin()
    
    st.markdown("### 📦 Module Management")
    st.markdown("View and manage system modules")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📋 All Modules", "🔄 Toggle Status", "↕️ Adjust Order"])
    
    with tab1:
        show_all_modules()
    
    with tab2:
        show_toggle_module_status()
    
    with tab3:
        show_adjust_module_order()


def show_all_modules():
    """Display all modules with their current status"""
    st.markdown("#### All Registered Modules")
    
    modules = ModuleDB.get_all_modules()
    
    if modules:
        # Create a nice display dataframe
        df = pd.DataFrame(modules)
        df_display = df[['icon', 'module_name', 'module_key', 'description', 'is_active', 'display_order']].copy()
        df_display.columns = ['Icon', 'Module Name', 'Key', 'Description', 'Status', 'Order']
        df_display['Status'] = df_display['Status'].map({True: '✅ Active', False: '❌ Inactive'})
        
        st.dataframe(df_display, width='stretch', hide_index=True)
        
        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Modules", len(modules))
        with col2:
            active_count = sum(1 for m in modules if m['is_active'])
            st.metric("Active Modules", active_count)
        with col3:
            inactive_count = len(modules) - active_count
            st.metric("Inactive Modules", inactive_count)
    else:
        st.info("No modules found in the system")
        st.markdown("**To add a new module:** Run the SQL registration script in Supabase")


def show_toggle_module_status():
    """Interface to toggle module active/inactive status"""
    st.markdown("#### Toggle Module Status")
    st.info("💡 Inactive modules will not appear in the sidebar for any users")
    
    modules = ModuleDB.get_all_modules()
    
    if not modules:
        st.warning("No modules found")
        return
    
    # Create selection options
    module_options = {f"{m['icon']} {m['module_name']} ({'✅ Active' if m['is_active'] else '❌ Inactive'})": m for m in modules}
    
    selected_key = st.selectbox(
        "Select Module to Toggle",
        options=list(module_options.keys()),
        help="Choose a module to activate or deactivate"
    )
    
    selected_module = module_options[selected_key]
    
    # Display current status
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**Module:** {selected_module['module_name']}")
        st.caption(f"Key: `{selected_module['module_key']}`")
        st.caption(f"Description: {selected_module.get('description', 'No description')}")
    
    with col2:
        current_status = selected_module['is_active']
        st.markdown(f"**Current Status:**")
        st.markdown(f"{'✅ Active' if current_status else '❌ Inactive'}")
    
    st.markdown("---")
    
    # Toggle button
    new_status = not current_status
    button_text = "🔴 Deactivate Module" if current_status else "🟢 Activate Module"
    button_type = "secondary" if current_status else "primary"
    
    if st.button(button_text, type=button_type, width='stretch'):
        if ModuleDB.toggle_module_status(selected_module['id'], new_status):
            status_text = "activated" if new_status else "deactivated"
            st.success(f"✅ Module '{selected_module['module_name']}' has been {status_text}!")
            
            # Log admin action
            admin_user = SessionManager.get_user()
            ActivityLogger.log(
                user_id=admin_user['id'],
                action_type='admin_action',
                description=f"{'Activated' if new_status else 'Deactivated'} module: {selected_module['module_name']}",
                metadata={'module_key': selected_module['module_key'], 'new_status': new_status}
            )
            
            st.rerun()
        else:
            st.error("Failed to update module status")


def show_adjust_module_order():
    """Interface to adjust module display order in sidebar"""
    st.markdown("#### Adjust Display Order")
    st.info("💡 Modules are displayed in the sidebar according to their display order (lower numbers appear first)")
    
    modules = ModuleDB.get_all_modules()
    
    if not modules:
        st.warning("No modules found")
        return
    
    # Sort by current display order
    modules_sorted = sorted(modules, key=lambda x: x['display_order'])
    
    st.markdown("**Current Order:**")
    
    # Display current order with ability to reorder
    new_orders = {}
    
    for idx, module in enumerate(modules_sorted, 1):
        col1, col2, col3 = st.columns([1, 4, 2])
        
        with col1:
            st.markdown(f"**{module['display_order']}**")
        
        with col2:
            st.markdown(f"{module['icon']} {module['module_name']}")
            st.caption(f"`{module['module_key']}`")
        
        with col3:
            new_order = st.number_input(
                "Order",
                min_value=1,
                max_value=99,
                value=module['display_order'],
                key=f"order_{module['id']}",
                label_visibility="collapsed"
            )
            new_orders[module['id']] = new_order
    
    st.markdown("---")
    
    # Check if any changes were made
    changes_made = any(
        new_orders[m['id']] != m['display_order'] 
        for m in modules_sorted
    )
    
    if changes_made:
        if st.button("💾 Save New Order", type="primary", width='stretch'):
            success_count = 0
            for module_id, new_order in new_orders.items():
                if ModuleDB.update_module_order(module_id, new_order):
                    success_count += 1
            
            st.success(f"✅ Updated display order for {success_count} modules!")
            
            # Log admin action
            admin_user = SessionManager.get_user()
            ActivityLogger.log(
                user_id=admin_user['id'],
                action_type='admin_action',
                description=f"Adjusted module display order ({success_count} modules)",
                metadata={'changes': success_count}
            )
            
            st.rerun()
    else:
        st.info("No changes detected. Adjust the order numbers above to reorder modules.")
