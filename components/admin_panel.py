"""
Admin panel components for user and permission management
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from config.database import Database, UserDB, RoleDB, ModuleDB, ActivityLogger
from auth.session import SessionManager

def show_user_management():
    """Admin panel for managing users"""
    SessionManager.require_admin()
    
    st.markdown("### 👥 User Management")
    st.markdown("Manage user accounts, roles, and access")
    st.markdown("---")
    
    # Tabs for different user management functions
    tab1, tab2, tab3 = st.tabs(["All Users", "Add New User", "User Activity"])
    
    with tab1:
        show_all_users()
    
    with tab2:
        show_add_user_form()
    
    with tab3:
        show_user_activity()


def show_all_users():
    """Display all users with edit/deactivate options"""
    users = UserDB.get_all_users()
    
    if users:
        # Convert to DataFrame for better display
        df = pd.DataFrame(users)
        df = df[['email', 'full_name', 'role_name', 'is_active', 'created_at']]
        df.columns = ['Email', 'Full Name', 'Role', 'Active', 'Created At']
        df['Created At'] = pd.to_datetime(df['Created At']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### Edit User")
        
        # Select user to edit
        user_emails = [u['email'] for u in users]
        selected_email = st.selectbox("Select user to edit", user_emails)
        
        if selected_email:
            selected_user = next(u for u in users if u['email'] == selected_email)
            show_edit_user_form(selected_user)
    else:
        st.info("No users found in the system.")


def show_edit_user_form(user):
    """Form to edit user details"""
    roles = RoleDB.get_all_roles()
    role_options = {r['role_name']: r['id'] for r in roles}
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_name = st.text_input("Full Name", value=user.get('full_name', ''))
        new_role = st.selectbox(
            "Role",
            options=list(role_options.keys()),
            index=list(role_options.keys()).index(user['role_name'])
        )
    
    with col2:
        is_active = st.checkbox("Active", value=user['is_active'])
        
        if st.button("Update User", type="primary"):
            updates = {
                'full_name': new_name,
                'role_id': role_options[new_role],
                'is_active': is_active
            }
            
            if UserDB.update_user_profile(user['id'], updates):
                st.success(f"User {user['email']} updated successfully!")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Updated user {user['email']}",
                    metadata={'target_user': user['email'], 'updates': updates}
                )
                
                st.rerun()
            else:
                st.error("Failed to update user")


def show_add_user_form():
    """Form to add new user"""
    st.markdown("#### Add New User")
    st.info("Note: User will receive an email from Supabase to set their password.")
    
    roles = RoleDB.get_all_roles()
    role_options = {r['role_name']: r['id'] for r in roles}
    
    with st.form("add_user_form"):
        email = st.text_input("Email *", placeholder="user@example.com")
        full_name = st.text_input("Full Name *", placeholder="John Doe")
        role = st.selectbox("Role *", options=list(role_options.keys()))
        
        submitted = st.form_submit_button("Create User", type="primary")
        
        if submitted:
            if not email or not full_name:
                st.error("Please fill in all required fields")
            else:
                create_new_user(email, full_name, role_options[role])


def create_new_user(email: str, full_name: str, role_id: int):
    """Create new user in Supabase"""
    try:
        supabase = Database.get_client()
        
        # Create user in Supabase Auth
        # Note: This requires admin privileges (service_role key)
        response = supabase.auth.admin.create_user({
            "email": email,
            "email_confirm": True,  # Auto-confirm email
            "user_metadata": {"full_name": full_name}
        })
        
        if response.user:
            # Create user profile
            if UserDB.create_user_profile(response.user.id, email, full_name, role_id):
                st.success(f"User {email} created successfully!")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Created new user {email}",
                    metadata={'new_user_email': email, 'role_id': role_id}
                )
                
                st.rerun()
            else:
                st.error("User created but profile creation failed")
        else:
            st.error("Failed to create user")
            
    except Exception as e:
        st.error(f"Error creating user: {str(e)}")


def show_user_activity():
    """Show recent activity for all users"""
    st.markdown("#### Recent User Activity")
    
    limit = st.slider("Number of records", 10, 200, 50)
    logs = ActivityLogger.get_all_activity(limit=limit)
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[['created_at', 'user_email', 'action_type', 'module_key', 'description']]
        df.columns = ['Timestamp', 'User', 'Action', 'Module', 'Description']
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            action_filter = st.multiselect(
                "Filter by Action Type",
                options=df['Action'].unique().tolist()
            )
        with col2:
            user_filter = st.multiselect(
                "Filter by User",
                options=df['User'].unique().tolist()
            )
        
        # Apply filters
        if action_filter:
            df = df[df['Action'].isin(action_filter)]
        if user_filter:
            df = df[df['User'].isin(user_filter)]
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No activity logs found")


def show_role_permissions():
    """Admin panel for managing role permissions"""
    SessionManager.require_admin()
    
    st.markdown("### 🔐 Role Permissions")
    st.markdown("Manage which modules each role can access")
    st.markdown("---")
    
    roles = RoleDB.get_all_roles()
    modules = ModuleDB.get_all_modules()
    
    if not roles or not modules:
        st.error("No roles or modules found in the system")
        return
    
    # Create permission matrix
    st.markdown("#### Permission Matrix")
    st.markdown("✅ = Can Access | ❌ = No Access")
    
    # Build matrix data
    matrix_data = []
    for module in modules:
        row = {'Module': f"{module.get('icon', '⚙️')} {module['module_name']}"}
        for role in roles:
            permissions = RoleDB.get_role_permissions(role['id'])
            has_access = any(
                p['module_id'] == module['id'] and p['can_access'] 
                for p in permissions
            )
            row[role['role_name']] = '✅' if has_access else '❌'
        matrix_data.append(row)
    
    df = pd.DataFrame(matrix_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("#### Edit Permissions")
    
    # Edit permissions
    col1, col2 = st.columns(2)
    
    with col1:
        selected_role = st.selectbox(
            "Select Role",
            options=[r['role_name'] for r in roles]
        )
    
    with col2:
        selected_module = st.selectbox(
            "Select Module",
            options=[f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules]
        )
    
    # Get selected role and module IDs
    role_id = next(r['id'] for r in roles if r['role_name'] == selected_role)
    module_idx = [f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules].index(selected_module)
    module_id = modules[module_idx]['id']
    
    # Check current permission
    permissions = RoleDB.get_role_permissions(role_id)
    current_access = any(p['module_id'] == module_id and p['can_access'] for p in permissions)
    
    can_access = st.checkbox("Allow Access", value=current_access)
    
    if st.button("Update Permission", type="primary"):
        if RoleDB.update_role_permission(role_id, module_id, can_access):
            st.success(f"Permission updated for {selected_role}!")
            
            # Log admin action
            admin_user = SessionManager.get_user()
            ActivityLogger.log(
                user_id=admin_user['id'],
                action_type='admin_action',
                description=f"Updated permission: {selected_role} -> {modules[module_idx]['module_name']}",
                metadata={'role': selected_role, 'module': modules[module_idx]['module_name'], 'access': can_access}
            )
            
            st.rerun()
        else:
            st.error("Failed to update permission")


def show_activity_logs():
    """Admin panel for viewing activity logs"""
    SessionManager.require_admin()
    
    st.markdown("### 📋 Activity Logs")
    st.markdown("View system-wide activity and audit trail")
    st.markdown("---")
    
    # Tabs for different log views
    tab1, tab2 = st.tabs(["All Activity", "Module Activity"])
    
    with tab1:
        show_all_activity_logs()
    
    with tab2:
        show_module_activity_logs()


def show_all_activity_logs():
    """Show all activity logs with filters"""
    st.markdown("#### All Activity")
    
    col1, col2 = st.columns(2)
    with col1:
        limit = st.slider("Number of records", 10, 500, 100)
    with col2:
        if st.button("Refresh Logs"):
            st.rerun()
    
    logs = ActivityLogger.get_all_activity(limit=limit)
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[['created_at', 'user_email', 'action_type', 'module_key', 'description', 'success']]
        df.columns = ['Timestamp', 'User', 'Action', 'Module', 'Description', 'Success']
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['Success'] = df['Success'].map({True: '✅', False: '❌'})
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            action_filter = st.multiselect("Action Type", options=df['Action'].unique().tolist())
        with col2:
            user_filter = st.multiselect("User", options=df['User'].dropna().unique().tolist())
        with col3:
            success_filter = st.multiselect("Success", options=['✅', '❌'])
        
        # Apply filters
        if action_filter:
            df = df[df['Action'].isin(action_filter)]
        if user_filter:
            df = df[df['User'].isin(user_filter)]
        if success_filter:
            df = df[df['Success'].isin(success_filter)]
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Download logs
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Logs as CSV",
            data=csv,
            file_name=f"activity_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No activity logs found")


def show_module_activity_logs():
    """Show activity logs filtered by module"""
    st.markdown("#### Module-Specific Activity")
    
    modules = ModuleDB.get_all_modules()
    module_options = {f"{m.get('icon', '⚙️')} {m['module_name']}": m['module_key'] for m in modules}
    
    selected_module_display = st.selectbox("Select Module", options=list(module_options.keys()))
    selected_module_key = module_options[selected_module_display]
    
    limit = st.slider("Number of records", 10, 200, 50)
    
    logs = ActivityLogger.get_module_activity(selected_module_key, limit=limit)
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[['created_at', 'user_email', 'action_type', 'description']]
        df.columns = ['Timestamp', 'User', 'Action', 'Description']
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No activity logs found for this module")


def show_module_management():
    """Admin panel for managing modules"""
    SessionManager.require_admin()
    
    st.markdown("### 📦 Module Management")
    st.markdown("Add new modules or modify existing ones")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["All Modules", "Add New Module"])
    
    with tab1:
        show_all_modules()
    
    with tab2:
        show_add_module_form()


def show_all_modules():
    """Display all modules"""
    modules = ModuleDB.get_all_modules()
    
    if modules:
        df = pd.DataFrame(modules)
        df = df[['icon', 'module_name', 'module_key', 'description', 'is_active', 'display_order']]
        df.columns = ['Icon', 'Name', 'Key', 'Description', 'Active', 'Order']
        df['Active'] = df['Active'].map({True: '✅', False: '❌'})
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No modules found")


def show_add_module_form():
    """Form to add new module"""
    st.markdown("#### Add New Module")
    st.info("After adding a module, you'll need to create the corresponding Python file in the modules/ directory")
    
    with st.form("add_module_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            module_name = st.text_input("Module Name *", placeholder="My New Module")
            module_key = st.text_input("Module Key *", placeholder="my_new_module", 
                                      help="Lowercase, underscores only. Must match Python filename.")
        
        with col2:
            icon = st.text_input("Icon (Emoji)", value="⚙️")
            display_order = st.number_input("Display Order", min_value=1, value=99)
        
        description = st.text_area("Description", placeholder="Describe what this module does")
        
        submitted = st.form_submit_button("Add Module", type="primary")
        
        if submitted:
            if not module_name or not module_key:
                st.error("Please fill in all required fields")
            elif ' ' in module_key or not module_key.replace('_', '').isalnum():
                st.error("Module key must be lowercase with underscores only")
            else:
                if ModuleDB.add_module(module_name, module_key, description, icon, display_order):
                    st.success(f"Module '{module_name}' added successfully!")
                    st.info(f"Next step: Create modules/{module_key}.py in your codebase")
                    
                    # Log admin action
                    admin_user = SessionManager.get_user()
                    ActivityLogger.log(
                        user_id=admin_user['id'],
                        action_type='admin_action',
                        description=f"Added new module: {module_name}",
                        metadata={'module_key': module_key}
                    )
                    
                    st.rerun()
                else:
                    st.error("Failed to add module")
