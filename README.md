# 📱 Multi-App Dashboard

A Streamlit-based multi-application dashboard with user authentication, role-based access control, and activity logging powered by Supabase.

## 🌟 Features

- **User Authentication** with Supabase Auth
- **Role-Based Access Control** (Admin, Manager, User)
- **Module Permission Management**
- **Activity Logging & Audit Trail**
- **Admin Panel** for user and permission management
- **Modular Architecture** - Easy to add new apps
- **Sidebar Navigation**
- **Responsive UI**

## 📋 Current Modules

1. **Order Extractor** - Extract orders between dates to Excel
2. **Shipping Label Generator** - Generate shipping labels PDF from Excel
3. **MRP Label Generator** - Consolidate MRP labels based on quantities
4. **WooCommerce to Zoho Export** - Generate CSV for Zoho import
5. **Website Stock & Price Updater** - Update stock and prices

## 🚀 Setup Instructions

### 1. Database Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Go to SQL Editor in your Supabase dashboard
3. Run the SQL schema from `database/schema.sql` (in artifacts)
4. Update modules with your actual apps using the update SQL provided

### 2. GitHub Repository Setup

```bash
# Create the following structure:
multi-app-dashboard/
├── .streamlit/
│   └── secrets.toml (don't commit!)
├── auth/
│   ├── __init__.py
│   ├── login.py
│   └── session.py
├── components/
│   ├── __init__.py
│   ├── admin_panel.py
│   ├── dashboard.py
│   └── sidebar.py
├── config/
│   ├── __init__.py
│   └── database.py
├── modules/
│   ├── __init__.py
│   ├── module_template.py
│   ├── order_extractor.py
│   ├── shipping_label_generator.py
│   ├── mrp_label_generator.py
│   ├── woocommerce_zoho_export.py
│   └── stock_price_updater.py
├── utils/
│   └── __init__.py
├── .gitignore
├── app.py
├── requirements.txt
└── README.md
```

### 3. Configure Secrets

#### For Local Development:
Create `.streamlit/secrets.toml`:

```toml
[supabase]
url = "https://your-project-id.supabase.co"
service_role_key = "your-service-role-key"
anon_key = "your-anon-key"

[api]
website_api_key = "your-api-key"
```

#### For Streamlit Cloud:
1. Go to your app settings on Streamlit Cloud
2. Click "Secrets"
3. Paste the same content as above
4. Click "Save"

### 4. Deploy to Streamlit Cloud

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "New app"
4. Select your repository
5. Set main file path: `app.py`
6. Add secrets in the Secrets section
7. Click "Deploy"

## 👥 User Management

### Creating the First Admin User

After deploying, you need to create your first admin user directly in Supabase:

1. Go to Supabase Dashboard → Authentication → Users
2. Click "Add User"
3. Enter email and password
4. Copy the user's UUID
5. Go to SQL Editor and run:

```sql
-- Replace USER_UUID with the actual UUID
INSERT INTO user_profiles (id, full_name, role_id, is_active)
VALUES (
    'USER_UUID',
    'Admin Name',
    (SELECT id FROM roles WHERE role_name = 'Admin'),
    TRUE
);
```

### Adding More Users

Once you have an admin account:
1. Login to the app
2. Go to Admin Panel → User Management
3. Click "Add New User" tab
4. Fill in the form and create users
5. Users will receive an email to set their password

## 🔧 Creating New Modules

### Step 1: Add Module to Database

Use the Admin Panel → Module Management, or run SQL:

```sql
INSERT INTO modules (module_name, module_key, description, icon, display_order)
VALUES ('My New Module', 'my_new_module', 'Description here', '🆕', 10);
```

### Step 2: Create Module File

Copy `modules/module_template.py` to `modules/my_new_module.py`:

```python
import streamlit as st
from auth import SessionManager
from config.database import ActivityLogger

def show():
    SessionManager.require_module_access('my_new_module')
    
    st.markdown("### 🆕 My New Module")
    # Your code here
```

### Step 3: Set Permissions

Go to Admin Panel → Role Permissions and enable access for appropriate roles.

## 🔐 Role Permissions

Default permissions:

| Module | Admin | Manager | User |
|--------|-------|---------|------|
| Order Extractor | ✅ | ✅ | ✅ |
| Shipping Label Generator | ✅ | ✅ | ✅ |
| MRP Label Generator | ✅ | ✅ | ❌ |
| WooCommerce to Zoho | ✅ | ✅ | ❌ |
| Stock & Price Updater | ✅ | ❌ | ❌ |
| Admin Panels | ✅ | ❌ | ❌ |

Customize these in the Admin Panel.

## 📊 Activity Logging

All user actions are automatically logged:
- Login/Logout
- Module access
- Admin actions
- Errors

View logs in: Admin Panel → Activity Logs

## 🛠️ Technology Stack

- **Frontend:** Streamlit
- **Backend:** Supabase (PostgreSQL)
- **Authentication:** Supabase Auth
- **Hosting:** Streamlit Cloud
- **Language:** Python 3.8+

## 📦 Dependencies

See `requirements.txt` for full list:
- streamlit
- supabase
- pandas
- reportlab (PDF generation)
- PyPDF2 (PDF manipulation)
- openpyxl (Excel operations)
- requests (API calls)

## 🔒 Security Best Practices

1. ✅ Never commit `.streamlit/secrets.toml`
2. ✅ Use Supabase service_role key (never expose publicly)
3. ✅ All passwords hashed by Supabase
4. ✅ Row Level Security enabled
5. ✅ Activity logging for audit trail
6. ✅ Role-based access control

## 🐛 Troubleshooting

### "Failed to connect to database"
- Check your Supabase URL and keys in secrets
- Ensure Supabase project is active

### "User profile not found"
- Ensure user_profiles entry exists for the user
- Check user's role is assigned

### "Access denied" errors
- Check role_permissions table
- Verify user's role has access to the module

### Module not loading
- Check module file exists: `modules/{module_key}.py`
- Ensure module has a `show()` function
- Check for syntax errors in module code

## 📞 Support

For issues:
1. Check Activity Logs in Admin Panel
2. Review Supabase logs
3. Check Streamlit Cloud logs
4. Contact your system administrator

## 📝 License

[Your License Here]

## 👨‍💻 Development

To add your existing mini apps:
1. Copy your existing code
2. Wrap it in a `show()` function
3. Add `SessionManager.require_module_access(module_key)`
4. Add activity logging at key points
5. Test with different user roles

---

Built with ❤️ using Streamlit and Supabase
