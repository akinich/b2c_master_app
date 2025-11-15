"""
Main application entry point
Multi-App Dashboard with Authentication and Role-Based Access

VERSION HISTORY:
1.3.0 - Simplified password reset to match farm-2-app - 11/15/25
      CHANGES:
      - Removed special app.py routing for password reset
      - Login page now handles all password reset flows
      - Simplified to match farm-2-app's proven pattern
1.2.0 - Added password reset completion handler - 11/15/25
      ADDITIONS:
      - Added query parameter detection for password reset flow
      - Integrated show_password_reset_completion for setting new password
      - Handles redirect from email link via static/redirect.html
1.1.0 - Enhanced security with whitelisted module loading - 11/12/25
      SECURITY IMPROVEMENTS:
      - Added whitelist for allowed modules (prevents code injection)
      - Replaced __import__ with importlib for safer module loading
      - Added explicit authentication/authorization checks
      - Sanitized error messages to prevent information disclosure
1.0.0 - Initial multi-app dashboard with role-based access - 11/11/25
KEY FUNCTIONS:
- Dynamic module loading with require_access checks
- Sidebar navigation with admin panel
- User authentication and session management
- Breadcrumb navigation
"""
import streamlit as st
import importlib
from auth import (
    SessionManager,
    show_login_page,
    show_logout_button,
    show_user_info
)
from components.sidebar import show_sidebar, show_module_breadcrumb
from components.dashboard import show_dashboard
from components.admin_panel import (
    show_user_management,
    show_user_permissions,  # ← CHANGED from show_role_permissions
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
SessionManager.init_session()

# SECURITY: Whitelist of allowed modules
# Only modules in this set can be loaded dynamically
ALLOWED_MODULES = {
    'order_extractor',
    'stock_price_updater',
    'product_management',
    'woocommerce_zoho_export',
    'shipping_label_generator',
    'mrp_label_generator',
    'module_template'  # Template for creating new modules
}

def load_module(module_key: str):
    """
    Securely load and display a module with validation

    Args:
        module_key: The key of the module to load (e.g., 'mrp_label_generator')

    Security:
        - Validates module_key against whitelist (prevents code injection)
        - Checks user authentication before loading
        - Checks user authorization for the specific module
        - Uses importlib instead of __import__ for safer importing
    """
    try:
        # SECURITY: Check if user is authenticated
        if not SessionManager.is_logged_in():
            st.error("Authentication required")
            st.stop()

        # SECURITY: Validate module_key against whitelist
        if module_key not in ALLOWED_MODULES:
            st.error("Access denied: Invalid module")
            # Log security event
            user = SessionManager.get_user()
            if user:
                from config.database import ActivityLogger
                ActivityLogger.log(
                    user_id=user['id'],
                    action_type='security_violation',
                    module_key='system',
                    description=f"Attempted to access invalid module: {module_key}"
                )
            st.stop()

        # SECURITY: Check if user has access to this module
        if not SessionManager.has_module_access(module_key):
            st.error("Access denied: You don't have permission to access this module")
            st.stop()

        # Import the module using importlib (safer than __import__)
        module = importlib.import_module(f'modules.{module_key}')

        # Check if module has a 'show' function
        if hasattr(module, 'show'):
            module.show()
        else:
            st.error("Module configuration error")
            st.info("Please contact administrator")

    except ModuleNotFoundError:
        st.error("Module not found")
        st.info("Please contact administrator if this module should be available")

    except Exception as e:
        # SECURITY: Don't expose internal error details to user
        st.error("An error occurred while loading the module")

        # Log error securely (server-side only)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading module {module_key}: {str(e)}", exc_info=True)


def main():
    """Main application logic"""

    # Check if user is authenticated
    # Note: login page handles password reset flow internally via extract_recovery_token()
    if not SessionManager.is_logged_in():
        # Show login page (which handles both login and password reset)
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
    if current_module is None or current_module == 'dashboard':
        # Show dashboard
        show_dashboard()

    elif current_module == 'admin_users':
        # Admin: User Management
        show_user_management()

    elif current_module == 'admin_permissions':
        # Admin: User Permissions (CHANGED from Role Permissions)
        show_user_permissions()

    elif current_module == 'admin_logs':
        # Admin: Activity Logs
        show_activity_logs()

    elif current_module == 'admin_modules':
        # Admin: Module Management
        show_module_management()

    else:
        # Load regular module
        load_module(current_module)


if __name__ == "__main__":
    main()
