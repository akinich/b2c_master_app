"""
Main application entry point
Multi-App Dashboard with Authentication and Role-Based Access
"""
import streamlit as st
from auth import SessionManager, show_login_page, show_logout_button, show_user_info
from components.sidebar import show_sidebar, show_module_breadcrumb
from components.dashboard import show_dashboard
from components.admin_panel import (
    show_user_management,
    show_role_permissions,
    show_activity_logs,
    show_module_management
)

# Page configuration
st.set_page_config(
    page_title="Multi-App Dashboard",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session
SessionManager.initialize_session()

def load_module(module_key: str):
    """
    Dynamically load and display a module
    Args:
        module_key: The key of the module to load (e.g., 'order_extractor')
    """
    try:
        # Import the module dynamically
        module = __import__(f'modules.{module_key}', fromlist=['show'])
        
        # Check if module has a 'show' function
        if hasattr(module, 'show'):
            module.show()
        else:
            st.error(f"Module '{module_key}' does not have a 'show()' function")
            st.info("Each module file must contain a show() function as the entry point")
    
    except ModuleNotFoundError:
        st.error(f"Module '{module_key}' not found")
        st.info(f"Please create the file: modules/{module_key}.py")
        st.code(f"""
# modules/{module_key}.py

import streamlit as st
from auth import SessionManager
from config.database import ActivityLogger

def show():
    '''Main function for {module_key} module'''
    
    # Ensure user has access
    SessionManager.require_module_access('{module_key}')
    
    st.markdown("## Your Module Content Here")
    st.write("Build your module functionality here...")
    
    # Example: Log module usage
    user = SessionManager.get_user()
    ActivityLogger.log(
        user_id=user['id'],
        action_type='module_use',
        module_key='{module_key}',
        description="User used {module_key} module"
    )
        """, language='python')
    
    except Exception as e:
        st.error(f"Error loading module: {str(e)}")
        st.exception(e)


def main():
    """Main application logic"""
    
    # Check if user is authenticated
    if not SessionManager.is_authenticated():
        # Show login page
        show_login_page()
        return
    
    # User is authenticated - show main app
    # Display sidebar navigation
    show_sidebar()
    
    # Display user info in sidebar
    show_user_info()
    
    # Display logout button
    show_logout_button()
    
    # Get current module
    current_module = SessionManager.get_current_module()
    
    # Show breadcrumb
    show_module_breadcrumb()
    
    # Route to appropriate page
    if current_module is None:
        # Show dashboard
        show_dashboard()
    
    elif current_module == 'admin_users':
        # Admin: User Management
        show_user_management()
    
    elif current_module == 'admin_permissions':
        # Admin: Role Permissions
        show_role_permissions()
    
    elif current_module == 'admin_logs':
        # Admin: Activity Logs
        show_activity_logs()
    
    elif current_module == 'admin_modules':
        # Admin: Module Management
        show_module_management()
    
    else:
        # Load the requested module
        load_module(current_module)


if __name__ == "__main__":
    main()
