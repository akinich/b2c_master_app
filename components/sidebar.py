"""
Sidebar navigation component
"""
import streamlit as st
from auth.session import SessionManager

def show_sidebar():
    """Display sidebar navigation with modules"""
    
    with st.sidebar:
        # App title/logo
        st.markdown("# 📱 Multi-App Dashboard")
        st.markdown("---")
        
        # Get user's accessible modules
        modules = SessionManager.get_accessible_modules()
        current_module = SessionManager.get_current_module()
        
        # Dashboard home button
        if st.button("🏠 Dashboard", use_container_width=True, 
                    type="primary" if current_module is None else "secondary"):
            st.session_state.current_module = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📦 Modules")
        
        # Display accessible modules
        if modules:
            for module in modules:
                module_key = module['module_key']
                module_name = module['module_name']
                icon = module.get('icon', '⚙️')
                
                # Highlight current module
                button_type = "primary" if current_module == module_key else "secondary"
                
                if st.button(
                    f"{icon} {module_name}",
                    key=f"nav_{module_key}",
                    use_container_width=True,
                    type=button_type
                ):
                    SessionManager.set_current_module(module_key)
                    st.rerun()
        else:
            st.info("No modules available for your role.")
        
        # Admin Panel (only for admins)
        if SessionManager.is_admin():
            st.markdown("---")
            st.markdown("### ⚙️ Administration")
            
            if st.button("👥 User Management", use_container_width=True,
                        type="primary" if current_module == 'admin_users' else "secondary"):
                st.session_state.current_module = 'admin_users'
                st.rerun()
            
            if st.button("🔐 Role Permissions", use_container_width=True,
                        type="primary" if current_module == 'admin_permissions' else "secondary"):
                st.session_state.current_module = 'admin_permissions'
                st.rerun()
            
            if st.button("📋 Activity Logs", use_container_width=True,
                        type="primary" if current_module == 'admin_logs' else "secondary"):
                st.session_state.current_module = 'admin_logs'
                st.rerun()
            
            if st.button("📦 Module Management", use_container_width=True,
                        type="primary" if current_module == 'admin_modules' else "secondary"):
                st.session_state.current_module = 'admin_modules'
                st.rerun()


def show_module_breadcrumb():
    """Show current module breadcrumb"""
    current_module = SessionManager.get_current_module()
    
    if current_module:
        # Find module name
        modules = SessionManager.get_accessible_modules()
        module_name = "Unknown Module"
        module_icon = "⚙️"
        
        for module in modules:
            if module['module_key'] == current_module:
                module_name = module['module_name']
                module_icon = module.get('icon', '⚙️')
                break
        
        # Check if it's an admin module
        admin_modules = {
            'admin_users': ('👥', 'User Management'),
            'admin_permissions': ('
