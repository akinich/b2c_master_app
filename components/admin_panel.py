"""
Admin panel components for user and permission management
UPDATED FOR HYBRID PERMISSION SYSTEM (Admin + User with module-level permissions)
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import secrets
import string
from config.database import Database, UserDB, RoleDB, ModuleDB, UserPermissionDB, ActivityLogger
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
                st.success("User updated successfully!")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Updated user profile for {user['email']}",
                    metadata={'target_user_id': user['id'], 'updates': updates}
                )
                
                st.rerun()
            else:
                st.error("Failed to update user")
    
    # Add password reset button
    st.markdown("---")
    if st.button("🔑 Reset Password", key=f"reset_{user['id']}"):
        reset_user_password(user['id'], user['email'])


def reset_user_password(user_id: str, user_email: str):
    """Reset user password and display new temporary password"""
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
                st.info("📋 Next step: Go to 'User Permissions' tab to assign module access")
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
        for role in roles:
            st.markdown(f"- **{role['role_name']}**: {role.get('description', 'N/A')}")
    
    st.code("""
INSERT INTO user_profiles (id, full_name, role_id, is_active)
VALUES (
    'PASTE-USER-UUID-HERE',
    'User Full Name',
    (SELECT id FROM roles WHERE role_name = 'User'),  -- Or 'Admin'
    TRUE
);
    """, language="sql")
    
    st.markdown("""
    ### Step 3: Verify
    1. Refresh this page
    2. Go to "All Users" tab
    3. The new user should appear
    4. Share the email and password with the user
    5. **Go to 'User Permissions' tab to assign module access**
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


def show_user_permissions():
    """
    NEW: Admin panel for managing user-specific module permissions
    Replaces the old role_permissions function
    """
    SessionManager.require_admin()
    
    st.markdown("### 🔐 User Permissions")
    st.markdown("Manage module access for individual users")
    st.markdown("---")
    
    # Info box explaining the system
    st.info("""
    **Hybrid Permission System:**
    - **Admins**: Automatically have access to all modules
    - **Users**: Module access is assigned individually below
    """)
    
    # Get all non-admin users and modules
    users = UserDB.get_non_admin_users()
    modules = ModuleDB.get_active_modules()
    
    if not users:
        st.warning("No regular users found. Create users in the 'User Management' tab first.")
        return
    
    if not modules:
        st.error("No active modules found in the system")
        return
    
    # Tab interface for different views
    tab1, tab2 = st.tabs(["Manage Permissions", "Permission Overview"])
    
    with tab1:
        show_edit_user_permissions(users, modules)
    
    with tab2:
        show_permissions_matrix(users, modules)


def show_edit_user_permissions(users, modules):
    """Show form to edit permissions for a selected user"""
    st.markdown("#### Assign Module Access")
    
    # Select user
    user_options = {f"{u['full_name']} ({u['email']})": u for u in users}
    selected_user_display = st.selectbox("Select User", options=list(user_options.keys()))
    selected_user = user_options[selected_user_display]
    
    st.markdown("---")
    st.markdown(f"**Managing permissions for:** {selected_user['full_name']}")
    st.markdown(f"**Email:** {selected_user['email']}")
    st.markdown("---")
    
    # Get current permissions for this user
    current_perms = UserPermissionDB.get_user_permissions_detail(selected_user['id'])
    current_access = {p['module_key']: p['can_access'] for p in current_perms}
    
    # Create checkboxes for each module
    st.markdown("#### Select Modules:")
    selected_modules = []
    
    # Display in 2 columns
    cols = st.columns(2)
    for idx, module in enumerate(modules):
        with cols[idx % 2]:
            is_checked = current_access.get(module['module_key'], False)
            if st.checkbox(
                f"{module.get('icon', '⚙️')} {module['module_name']}",
                value=is_checked,
                key=f"perm_{selected_user['id']}_{module['id']}"
            ):
                selected_modules.append(module['id'])
    
    st.markdown("---")
    
    # Save button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("💾 Save Permissions", type="primary", use_container_width=True):
            admin_user = SessionManager.get_user()
            success = UserPermissionDB.bulk_update_user_permissions(
                selected_user['id'],
                selected_modules,
                admin_user['id']
            )
            
            if success:
                st.success("✅ Permissions updated successfully!")
                
                # Log the permission change
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='permission_change',
                    description=f"Updated permissions for {selected_user['email']}",
                    metadata={
                        'target_user_id': selected_user['id'],
                        'target_user_email': selected_user['email'],
                        'modules_granted': [m['module_key'] for m in modules if m['id'] in selected_modules],
                        'total_modules': len(selected_modules)
                    }
                )
                
                st.rerun()
            else:
                st.error("❌ Failed to update permissions")


def show_permissions_matrix(users, modules):
    """Show permission matrix for all users"""
    st.markdown("#### Permission Matrix")
    st.markdown("Overview of all user permissions")
    
    # Build matrix data
    matrix_data = []
    for user in users:
        row = {
            'User': f"{user['full_name']}",
            'Email': user['email']
        }
        
        # Get permissions for this user
        perms = UserPermissionDB.get_user_permissions_detail(user['id'])
        perm_dict = {p['module_key']: p['can_access'] for p in perms}
        
        for module in modules:
            has_access = perm_dict.get(module['module_key'], False)
            row[f"{module.get('icon', '⚙️')} {module['module_name']}"] = '✅' if has_access else '❌'
        
        matrix_data.append(row)
    
    if matrix_data:
        df = pd.DataFrame(matrix_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Summary stats
        st.markdown("---")
        st.markdown("#### Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Users", len(users))
        
        with col2:
            st.metric("Total Modules", len(modules))
        
        with col3:
            # Calculate average modules per user
            total_perms = sum(
                sum(1 for module in modules 
                    if any(p['module_key'] == module['module_key'] and p['can_access'] 
                          for p in UserPermissionDB.get_user_permissions_detail(user['id'])))
                for user in users
            )
            avg_modules = round(total_perms / len(users), 1) if users else 0
            st.metric("Avg Modules/User", avg_modules)
    else:
        st.info("No permission data available")


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
        
        # Export option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"activity_logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No activity logs found")


def show_module_activity_logs():
    """Show activity filtered by module"""
    st.markdown("#### Module Activity")
    
    modules = ModuleDB.get_all_modules()
    if not modules:
        st.error("No modules found")
        return
    
    selected_module = st.selectbox(
        "Select Module",
        options=[f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules]
    )
    
    module_idx = [f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules].index(selected_module)
    module_key = modules[module_idx]['module_key']
    
    limit = st.slider("Number of records", 10, 200, 50, key="module_log_limit")
    
    logs = ActivityLogger.get_module_activity(module_key, limit=limit)
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[['created_at', 'user_email', 'action_type', 'description', 'success']]
        df.columns = ['Timestamp', 'User', 'Action', 'Description', 'Success']
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['Success'] = df['Success'].map({True: '✅', False: '❌'})
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No activity logs found for {modules[module_idx]['module_name']}")


def show_module_management():
    """Admin panel for managing modules"""
    SessionManager.require_admin()
    
    st.markdown("### ⚙️ Module Management")
    st.markdown("Manage system modules")
    st.markdown("---")
    
    modules = ModuleDB.get_all_modules()
    
    if modules:
        df = pd.DataFrame(modules)
        display_cols = ['icon', 'module_name', 'module_key', 'description', 'is_active', 'display_order']
        df_display = df[display_cols].copy()
        df_display.columns = ['Icon', 'Name', 'Key', 'Description', 'Active', 'Order']
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### Toggle Module Status")
        
        selected_module = st.selectbox(
            "Select Module",
            options=[f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules]
        )
        
        module_idx = [f"{m.get('icon', '⚙️')} {m['module_name']}" for m in modules].index(selected_module)
        module = modules[module_idx]
        
        current_status = module['is_active']
        new_status = st.checkbox("Active", value=current_status, key=f"status_{module['id']}")
        
        if st.button("Update Status", type="primary"):
            if ModuleDB.toggle_module_status(module['id'], new_status):
                st.success(f"Module status updated!")
                
                # Log admin action
                admin_user = SessionManager.get_user()
                ActivityLogger.log(
                    user_id=admin_user['id'],
                    action_type='admin_action',
                    description=f"Changed module status: {module['module_name']} -> {'Active' if new_status else 'Inactive'}",
                    metadata={'module_id': module['id'], 'module_key': module['module_key'], 'new_status': new_status}
                )
                
                st.rerun()
            else:
                st.error("Failed to update module status")
    else:
        st.info("No modules found in the system")
    
    st.markdown("---")
    st.markdown("#### Add New Module")
    st.info("💡 After adding a module here, you need to create the actual module file in your code")
    
    with st.form("add_module_form"):
        module_name = st.text_input("Module Name *")
        module_key = st.text_input("Module Key * (lowercase, underscore separated)")
        description = st.text_area("Description")
        icon = st.text_input("Icon (emoji)", value="⚙️")
        display_order = st.number_input("Display Order", min_value=1, value=99)
        
        submitted = st.form_submit_button("➕ Add Module", type="primary")
        
        if submitted:
            if not module_name or not module_key:
                st.error("Please fill in required fields")
            else:
                if ModuleDB.add_module(module_name, module_key, description, icon, display_order):
                    st.success(f"Module {module_name} added successfully!")
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
