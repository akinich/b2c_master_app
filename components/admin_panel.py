"""
Admin Panel Components
Handles user management, permissions, activity logs, and module management
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict
from auth.session import SessionManager
from config.database import UserDB, ModuleDB, ActivityLogger, UserPermissionDB


def show_user_management():
    """Admin panel for managing users"""
    SessionManager.require_admin()
    
    st.markdown("### 👥 User Management")
    st.markdown("Manage user accounts and access")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["All Users", "Add New User"])
    
    with tab1:
        show_all_users()
    
    with tab2:
        show_add_user_form()


def show_all_users():
    """Display all users in the system"""
    users = UserDB.get_all_users()
    
    if users:
        df = pd.DataFrame(users)
        display_cols = ['email', 'full_name', 'role_name', 'is_active', 'created_at']
        df_display = df[display_cols].copy()
        df_display.columns = ['Email', 'Name', 'Role', 'Active', 'Created']
        df_display['Active'] = df_display['Active'].map({True: '✅', False: '❌'})
        df_display['Created'] = pd.to_datetime(df_display['Created']).dt.strftime('%Y-%m-%d')
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No users found")


def show_add_user_form():
    """Form to add new user"""
    st.markdown("#### Add New User")
    st.info("User will receive an email from Supabase to set their password")
    
    with st.form("add_user_form"):
        email = st.text_input("Email *", placeholder="user@example.com")
        full_name = st.text_input("Full Name *", placeholder="John Doe")
        
        roles = UserDB.get_all_roles()
        role_options = {role['role_name']: role['id'] for role in roles}
        selected_role = st.selectbox("Role *", options=list(role_options.keys()))
        
        submitted = st.form_submit_button("Create User", type="primary")
        
        if submitted:
            if not email or not full_name:
                st.error("Please fill in all required fields")
            else:
                role_id = role_options[selected_role]
                if UserDB.create_user(email, full_name, role_id):
                    st.success(f"User {email} created successfully!")
                    
                    # Log admin action
                    admin_user = SessionManager.get_user()
                    ActivityLogger.log(
                        user_id=admin_user['id'],
                        action_type='admin_action',
                        description=f"Created new user: {email}",
                        metadata={'email': email, 'role': selected_role}
                    )
                    
                    st.rerun()
                else:
                    st.error("Failed to create user")


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
    
    st.markdown(f"**Configuring permissions for:** {selected_user['email']}")
    st.markdown("---")
    
    # Get user's current permissions
    user_permissions = UserPermissionDB.get_user_permissions(selected_user['id'])
    user_module_access = {perm['modules']['id']: perm['can_access'] for perm in user_permissions if 'modules' in perm}
    
    # Display modules with checkboxes
    st.markdown("#### Module Access")
    
    changes_made = False
    
    for module in modules:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"{module['icon']} **{module['module_name']}**")
            st.caption(module.get('description', ''))
        
        with col2:
            current_access = user_module_access.get(module['id'], False)
            new_access = st.checkbox(
                "Access",
                value=current_access,
                key=f"perm_{selected_user['id']}_{module['id']}"
            )
            
            if new_access != current_access:
                changes_made = True
    
    # Save button
    if changes_made:
        if st.button("💾 Save Changes", type="primary"):
            success_count = 0
            admin_user = SessionManager.get_user()
            for module in modules:
                new_access = st.session_state.get(f"perm_{selected_user['id']}_{module['id']}", False)
                if UserPermissionDB.update_user_permission(
                    selected_user['id'], 
                    module['id'], 
                    new_access,
                    admin_user['id']
                ):
                    success_count += 1
            
            st.success(f"Updated {success_count} permissions for {selected_user['email']}")
            
            # Log admin action
            ActivityLogger.log(
                user_id=admin_user['id'],
                action_type='admin_action',
                description=f"Updated module permissions for {selected_user['email']}",
                metadata={'target_user': selected_user['email'], 'changes': success_count}
            )
            
            st.rerun()


def show_activity_logs():
    """Admin panel for viewing activity logs"""
    SessionManager.require_admin()
    
    st.markdown("### 📊 Activity Logs")
    st.markdown("View user activity across all modules")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        days_back = st.number_input("Days to show", min_value=1, max_value=90, value=7)
    
    with col2:
        users = UserDB.get_all_users()
        user_filter = st.selectbox("Filter by user", options=['All'] + [u['email'] for u in users])
    
    with col3:
        action_types = ['All', 'login', 'logout', 'module_access', 'admin_action', 'module_error']
        action_filter = st.selectbox("Filter by action", options=action_types)
    
    # Fetch logs
    logs = ActivityLogger.get_logs(days=days_back)
    
    if logs:
        df = pd.DataFrame(logs)
        
        # Apply filters
        if user_filter != 'All':
            df = df[df['user_email'] == user_filter]
        
        if action_filter != 'All':
            df = df[df['action_type'] == action_filter]
        
        if not df.empty:
            # Display
            display_df = df[['created_at', 'user_email', 'action_type', 'description', 'success']]
            display_df.columns = ['Timestamp', 'User', 'Action', 'Description', 'Success']
            display_df['Timestamp'] = pd.to_datetime(display_df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            display_df['Success'] = display_df['Success'].map({True: '✅', False: '❌', None: '-'})
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"activity_logs_{datetime.now().strftime('%Y%m%d')}.csv",
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
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No activity logs found for this module")


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
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
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
    
    if st.button(button_text, type=button_type, use_container_width=True):
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
        if st.button("💾 Save New Order", type="primary", use_container_width=True):
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
