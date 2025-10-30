"""
Admin panel components for user and permission management
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import secrets
import string
from config.database import Database, UserDB, RoleDB, ModuleDB, ActivityLogger
from auth.session import SessionManager

def show_user_management():
    """Admin panel for managing users"""
    SessionManager.require_admin()
    
    st.markdown("### 👥 User Management")
    st.markdown("Manage user accounts, roles, and access")
    st.markdown("---")
    
    # Tabs for different user management functions
    tab1, tab2, tab3, tab4 = st.tabs(["All Users", "Add New User", "User Activity", "Manual Add Instructions"])
    
    with tab1:
        show_all_users()
    
    with tab2:
        show_add_user_form()
    
    with tab3:
        show_user_activity()
    
    with tab4:
        show_manual_user_creation()


def show_all_users():
    """Display all users with edit/deactivate options"""
    users = UserDB.get_all_users()
    
    if users:
        # Convert to DataFrame for better display
        df = pd.DataFrame(users)
        display_cols = ['email', 'full_name', 'role_name', 'is_active', 'created_at']
        df_display = df[display_cols].copy()
        df_display.columns = ['Email', 'Full Name', 'Role', 'Active', 'Created At']
        df_display['Created At'] = pd.to_datetime(df_display['Created At']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
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
    if not roles:
        st.error("No roles found in system")
        return
    
    role_options = {r['role_name']: r['id'] for r in roles}
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_name = st.text_input("Full Name", value=user.get('full_name', ''), key=f"name_{user['id']}")
        
        # Get current role index safely
        current_role = user.get('role_name', 'User')
        role_names = list(role_options.keys())
        try:
            current_role_idx = role_names.index(current_role)
        except ValueError:
            current_role_idx = 0
        
        new_role = st.selectbox(
            "Role",
            options=role_names,
            index=current_role_idx,
            key=f"role_{user['id']}"
        )
    
    with col2:
        is_active = st.checkbox("Active", value=user.get('is_active', True), key=f"active_{user['id']}")
        
        if st.button("💾 Update User", type="primary", key=f"update_{user['id']}"):
            updates = {
                'full_name': new_name,
                'role_id': role_options[new_role],
                'is_active': is_active
            }
            
            if UserDB.update_user_profile(user['id'], updates):
                st.success(f"✅ User {user['email']} updated successfully!")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Updated user {user['email']} - Role: {new_role}, Active: {is_active}",
                    metadata={'target_user': user['email'], 'updates': updates}
                )
                
                # Force cache clear and rerun
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("❌ Failed to update user")
    
    # Password Reset Section
    st.markdown("---")
    st.markdown("#### 🔐 Password Reset")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("Generate a new temporary password for this user")
    
    with col2:
        if st.button("🔄 Reset Password", key=f"reset_pwd_{user['id']}", type="secondary", use_container_width=True):
            reset_user_password(user['id'], user['email'])
    
    # Delete User Section
    st.markdown("---")
    st.markdown("#### 🗑️ Delete User")
    
    st.warning("⚠️ **Danger Zone**: This action cannot be undone")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("Permanently delete this user from the system")
    
    with col2:
        if st.button("🗑️ Delete User", key=f"delete_{user['id']}", type="secondary", use_container_width=True):
            # Show confirmation
            st.session_state[f'confirm_delete_{user["id"]}'] = True
    
    # Confirmation for delete
    if st.session_state.get(f'confirm_delete_{user["id"]}', False):
        st.error(f"⚠️ Are you sure you want to delete {user['email']}?")
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("✅ Yes, Delete", key=f"confirm_yes_{user['id']}", type="primary"):
                delete_user(user['id'], user['email'])
                st.session_state[f'confirm_delete_{user["id"]}'] = False
        
        with col2:
            if st.button("❌ Cancel", key=f"confirm_no_{user['id']}"):
                st.session_state[f'confirm_delete_{user["id"]}'] = False
                st.rerun()


def delete_user(user_id: str, user_email: str):
    """Delete user from system"""
    try:
        supabase = Database.get_client()
        
        # First, delete user profile
        supabase.table('user_profiles').delete().eq('id', user_id).execute()
        
        # Then delete from auth (this will cascade)
        response = supabase.auth.admin.delete_user(user_id)
        
        st.success(f"✅ User {user_email} deleted successfully!")
        
        # Log admin action
        admin_user = SessionManager.get_user()
        ActivityLogger.log(
            user_id=admin_user['id'],
            action_type='admin_action',
            description=f"Deleted user {user_email}",
            metadata={'deleted_user_email': user_email}
        )
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error deleting user: {str(e)}")
        st.info("Try manually deleting in Supabase Dashboard → Authentication → Users")


def reset_user_password(user_id: str, user_email: str):
    """Reset user password and generate new temporary password"""
    try:
        supabase = Database.get_client()
        
        # Generate new temporary password
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # Update user password using admin API
        response = supabase.auth.admin.update_user_by_id(
            user_id,
            {"password": temp_password}
        )
        
        if response.user:
            st.success(f"✅ Password reset successfully for {user_email}")
            
            # Display new password
            st.markdown("---")
            st.warning("⚠️ **IMPORTANT: Share this new password securely with the user**")
            st.code(f"Email: {user_email}\nNew Password: {temp_password}", language="text")
            st.info("👉 User should change this password after logging in")
            st.markdown("---")
            
            # Log admin action
            admin_user = SessionManager.get_user()
            ActivityLogger.log(
                user_id=admin_user['id'],
                action_type='admin_action',
                description=f"Reset password for user {user_email}",
                metadata={'target_user_email': user_email}
            )
        else:
            st.error("❌ Failed to reset password")
            
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ Error: {error_msg}")
        
        if "not allowed" in error_msg.lower():
            st.warning("🔧 **Manual Reset Method:**")
            st.markdown("""
            1. Go to Supabase Dashboard → Authentication → Users
            2. Find user: `{}`
            3. Click ⋮ menu → "Send password recovery"
            """.format(user_email))


def show_add_user_form():
    """Form to add new user"""
    st.markdown("#### Add New User")
    
    # Check rate limit info
    st.info("💡 If you get 'User not allowed' error, use the 'Manual Add Instructions' tab or wait a few minutes and try again.")
    
    roles = RoleDB.get_all_roles()
    if not roles:
        st.error("No roles found")
        return
        
    role_options = {r['role_name']: r['id'] for r in roles}
    
    with st.form("add_user_form"):
        email = st.text_input("Email *", placeholder="user@example.com")
        full_name = st.text_input("Full Name *", placeholder="John Doe")
        role = st.selectbox("Role *", options=list(role_options.keys()))
        
        submitted = st.form_submit_button("➕ Create User", type="primary")
        
        if submitted:
            if not email or not full_name:
                st.error("Please fill in all required fields")
            else:
                create_new_user(email, full_name, role_options[role])


def create_new_user(email: str, full_name: str, role_id: int):
    """Create new user in Supabase"""
    try:
        supabase = Database.get_client()
        
        # Generate a strong temporary password
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # Create user using Supabase Admin API
        response = supabase.auth.admin.create_user({
            "email": email,
            "password": temp_password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name
            }
        })
        
        if response.user:
            user_id = response.user.id
            
            # Create user profile in our database
            success = UserDB.create_user_profile(user_id, email, full_name, role_id)
            
            if success:
                st.success(f"✅ User {email} created successfully!")
                
                # Display temporary password
                st.markdown("---")
                st.warning("⚠️ **IMPORTANT: Share these credentials securely**")
                st.code(f"Email: {email}\nPassword: {temp_password}", language="text")
                st.info("👉 User should change this password after first login")
                st.markdown("---")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Created new user: {email}",
                    metadata={'new_user_email': email, 'role_id': role_id}
                )
            else:
                st.error("❌ User created in auth but profile creation failed")
        else:
            st.error("❌ Failed to create user")
            
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ Error: {error_msg}")
        
        if "not allowed" in error_msg.lower() or "rate limit" in error_msg.lower():
            st.warning("⚠️ **Rate Limit or Permission Issue**")
            st.info("Please use the 'Manual Add Instructions' tab to create users manually")


def show_manual_user_creation():
    """Instructions for manually creating users"""
    st.markdown("#### 📋 Manual User Creation (Recommended for Multiple Users)")
    
    st.markdown("""
    If you're having issues with automatic user creation, follow these steps:
    
    ### Step 1: Create User in Supabase
    1. Go to **Supabase Dashboard** → **Authentication** → **Users**
    2. Click **"Add user"** button
    3. Fill in:
       - **Email:** User's email
       - **Password:** Create a password
       - **Auto Confirm User:** ✅ **Check this box**
    4. Click **"Create user"**
    5. **Copy the User UUID** from the users list
    
    ### Step 2: Add User Profile
    1. Go to **SQL Editor** in Supabase
    2. Click **"New Query"**
    3. Paste the SQL below and fill in the details:
    """)
    
    # Show roles for reference
    roles = RoleDB.get_all_roles()
    if roles:
        st.markdown("**Available Roles:**")
        role_info = {r['role_name']: r['id'] for r in roles}
        for role_name, role_id in role_info.items():
            st.code(f"{role_name} (ID: {role_id})")
    
    st.markdown("### SQL Template:")
    
    sql_template = """-- Replace the values below:
-- USER-UUID: The UUID you copied from step 1
-- Full Name: User's full name
-- ROLE-ID: Use the role ID from above (1=Admin, 2=Manager, 3=User)

INSERT INTO user_profiles (id, full_name, role_id, is_active)
VALUES (
    'USER-UUID-HERE',  -- Replace with UUID
    'User Full Name',   -- Replace with name
    3,                  -- Replace with role ID (1, 2, or 3)
    TRUE
);"""
    
    st.code(sql_template, language="sql")
    
    st.markdown("""
    ### Step 3: Verify
    1. Refresh this page
    2. Go to "All Users" tab
    3. The new user should appear
    4. Share the email and password with the user
    """)
    
    st.success("💡 This method bypasses API rate limits and is more reliable!")


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
    
    if not modules:
        st.info("No modules found")
        return
    
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
