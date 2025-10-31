"""
Main dashboard view
"""
import streamlit as st
from auth.session import SessionManager

def show_dashboard():
    """Display main dashboard with welcome message and quick access"""
    
    profile = SessionManager.get_user_profile()
    user = SessionManager.get_user()
    modules = SessionManager.get_accessible_modules()
    
    # Welcome message
    st.markdown(f"### Welcome back, {profile.get('full_name', user.get('email'))}! 👋")
    st.markdown("---")
    
    # Quick stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Your Role", value=profile.get('role_name', 'N/A'))
    
    with col2:
        st.metric(label="Available Modules", value=len(modules))
    
    with col3:
        if SessionManager.is_admin():
            st.metric(label="Access Level", value="Full Access", delta="Admin")
        else:
            st.metric(label="Access Level", value="Limited Access")
    
    st.markdown("---")
    
    # Quick access to modules
    st.markdown("### 🚀 Quick Access")
    
    if modules:
        # Display modules in a grid
        cols = st.columns(2)
        
        for idx, module in enumerate(modules):
            with cols[idx % 2]:
                with st.container():
                    st.markdown(f"#### {module.get('icon', '⚙️')} {module['module_name']}")
                    st.write(module.get('description', 'No description available'))
                    
                    if st.button("Open", key=f"open_{module['module_key']}", use_container_width=True):
                        SessionManager.set_current_module(module['module_key'])
                        st.rerun()
                    
                    st.markdown("---")
    else:
        st.info("No modules available. Contact your administrator for access.")
    
    # Additional info for admins
    if SessionManager.is_admin():
        st.markdown("---")
        st.markdown("### ⚙️ Admin Quick Links")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("👥 Manage Users", use_container_width=True, type="secondary"):
                st.session_state.current_module = 'admin_users'
                st.rerun()
        
        with col2:
            if st.button("📋 View Activity Logs", use_container_width=True, type="secondary"):
                st.session_state.current_module = 'admin_logs'
                st.rerun()
