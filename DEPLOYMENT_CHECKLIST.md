# 🚀 Deployment Checklist

Follow this checklist step-by-step to deploy your Multi-App Dashboard.

## ✅ Phase 1: Supabase Setup (COMPLETED)

- [x] Created Supabase project
- [x] Ran initial schema SQL
- [x] Updated modules with actual app names
- [x] Got Project URL and API keys

## ✅ Phase 2: GitHub Repository Setup

### Step 1: Create Repository
- [ ] Create new repository on GitHub
- [ ] Name it: `multi-app-dashboard` (or your preferred name)
- [ ] Set to Private (recommended) or Public

### Step 2: Add Files to GitHub

Create these files in order (I've provided all the code):

**Root Files:**
- [ ] `.gitignore`
- [ ] `requirements.txt`
- [ ] `README.md`
- [ ] `DEPLOYMENT_CHECKLIST.md` (this file)
- [ ] `app.py`

**config/ folder:**
- [ ] `config/__init__.py`
- [ ] `config/database.py`

**auth/ folder:**
- [ ] `auth/__init__.py`
- [ ] `auth/session.py`
- [ ] `auth/login.py`

**components/ folder:**
- [ ] `components/__init__.py`
- [ ] `components/sidebar.py`
- [ ] `components/dashboard.py`
- [ ] `components/admin_panel.py`

**utils/ folder:**
- [ ] `utils/__init__.py`

**modules/ folder:**
- [ ] `modules/__init__.py`
- [ ] `modules/module_template.py`

### Step 3: Add Your Mini Apps
- [ ] Create `modules/order_extractor.py`
- [ ] Create `modules/shipping_label_generator.py`
- [ ] Create `modules/mrp_label_generator.py`
- [ ] Create `modules/woocommerce_zoho_export.py`
- [ ] Create `modules/stock_price_updater.py`

> **Note:** Share your existing module code with me, and I'll help you adapt them to work with this framework!

## ✅ Phase 3: Streamlit Cloud Deployment

### Step 1: Deploy App
- [ ] Go to [share.streamlit.io](https://share.streamlit.io)
- [ ] Sign in with GitHub
- [ ] Click "New app"
- [ ] Select your repository
- [ ] Branch: `main` (or your default branch)
- [ ] Main file path: `app.py`
- [ ] Click "Advanced settings"

### Step 2: Add Secrets
Copy and paste this into the Secrets section (replace with your actual values):

```toml
[supabase]
url = "https://your-project-id.supabase.co"
service_role_key = "your-service-role-key-here"
anon_key = "your-anon-key-here"

[api]
website_api_key = "your-website-api-key"
# Add other API keys as needed
```

- [ ] Added Supabase URL
- [ ] Added service_role_key
- [ ] Added anon_key
- [ ] Added website API key
- [ ] Added any other API keys your modules need

### Step 3: Deploy
- [ ] Click "Deploy"
- [ ] Wait for deployment (usually 2-5 minutes)
- [ ] Check for any errors in logs

## ✅ Phase 4: Create First Admin User

### Option A: Through Supabase Dashboard
1. [ ] Go to Supabase → Authentication → Users
2. [ ] Click "Add user"
3. [ ] Email: `your-admin-email@company.com`
4. [ ] Password: `create-secure-password`
5. [ ] Auto Confirm User: **YES**
6. [ ] Copy the user's UUID from the list
7. [ ] Go to SQL Editor and run:

```sql
INSERT INTO user_profiles (id, full_name, role_id, is_active)
VALUES (
    'PASTE-USER-UUID-HERE',
    'Your Name',
    (SELECT id FROM roles WHERE role_name = 'Admin'),
    TRUE
);
```

### Option B: Through SQL (All-in-one)
Run this in Supabase SQL Editor:

```sql
-- Create admin user (replace email and password)
-- Note: This requires service_role privileges
SELECT auth.create_user(
    jsonb_build_object(
        'email', 'admin@yourcompany.com',
        'password', 'YourSecurePassword123!',
        'email_confirm', true
    )
);

-- Get the user ID (will show in results above)
-- Then insert profile:
INSERT INTO user_profiles (id, full_name, role_id, is_active)
VALUES (
    'USER-ID-FROM-ABOVE',
    'Admin Name',
    (SELECT id FROM roles WHERE role_name = 'Admin'),
    TRUE
);
```

- [ ] Created first admin user
- [ ] Verified admin can login

## ✅ Phase 5: Test the Application

### Basic Tests:
- [ ] Login with admin account works
- [ ] Dashboard loads correctly
- [ ] Sidebar shows all modules
- [ ] Can navigate between modules
- [ ] Admin panel is accessible
- [ ] Logout works

### Admin Panel Tests:
- [ ] User Management page loads
- [ ] Can view all users
- [ ] Can add new user (test with a dummy email)
- [ ] Role Permissions page loads
- [ ] Can view permission matrix
- [ ] Activity Logs page loads
- [ ] Can see login activity
- [ ] Module Management page loads

### Module Tests:
- [ ] Each module loads without errors
- [ ] File uploads work (if applicable)
- [ ] Module functionality works correctly
- [ ] Can download generated files
- [ ] Activity is logged

## ✅ Phase 6: Add Team Members

For each team member:

1. [ ] Go to Admin Panel → User Management → Add New User
2. [ ] Enter their email
3. [ ] Enter their full name
4. [ ] Select appropriate role (Admin/Manager/User)
5. [ ] Click "Create User"
6. [ ] User receives email from Supabase
7. [ ] User clicks link to set password
8. [ ] Verify they can login

Repeat for all team members:
- [ ] Team Member 1: _______________
- [ ] Team Member 2: _______________
- [ ] Team Member 3: _______________
- [ ] Team Member 4: _______________
- [ ] Team Member 5: _______________

## ✅ Phase 7: Configure Permissions

- [ ] Review default role permissions
- [ ] Go to Admin Panel → Role Permissions
- [ ] Adjust permissions as needed:
  - [ ] Admin permissions configured
  - [ ] Manager permissions configured
  - [ ] User permissions configured
- [ ] Test with each role to verify access

## ✅ Phase 8: Final Verification

### Security Checks:
- [ ] `.streamlit/secrets.toml` is in `.gitignore`
- [ ] No sensitive data in GitHub repo
- [ ] Service role key is only in Streamlit Cloud secrets
- [ ] All users have strong passwords

### Performance Checks:
- [ ] App loads quickly
- [ ] File uploads work smoothly
- [ ] Module transitions are smooth
- [ ] No console errors

### User Experience:
- [ ] Navigation is intuitive
- [ ] Error messages are helpful
- [ ] Success messages appear
- [ ] Downloads work correctly

## 📋 Post-Deployment Tasks

### Documentation:
- [ ] Share app URL with team
- [ ] Share login instructions
- [ ] Document any module-specific instructions
- [ ] Create user guide (optional)

### Monitoring:
- [ ] Bookmark Streamlit Cloud dashboard
- [ ] Bookmark Supabase dashboard
- [ ] Set up alerts (optional)
- [ ] Schedule regular backups (optional)

### Maintenance:
- [ ] Plan for regular updates
- [ ] Monitor activity logs weekly
- [ ] Review user access monthly
- [ ] Update modules as needed

## 🎉 Deployment Complete!

Once all checkboxes are checked, your Multi-App Dashboard is live and ready to use!

## 📞 Need Help?

If you encounter issues:

1. **Check Streamlit Cloud Logs:**
   - Go to your app on Streamlit Cloud
   - Click "Manage app" → "Logs"

2. **Check Supabase Logs:**
   - Go to Supabase Dashboard
   - Click "Logs" in sidebar

3. **Common Issues:**
   - **Module not found:** Check file exists and `show()` function is defined
   - **Database errors:** Verify secrets are correct
   - **Login fails:** Check user exists in both auth.users and user_profiles
   - **Access denied:** Check role_permissions table

## 🔄 Next Steps

After successful deployment:
1. Share your existing module code with me
2. I'll help adapt each module to work with the framework
3. We'll test them one by one
4. Deploy updates to Streamlit Cloud

---

**Current Status:** Ready to deploy base framework ✅
**Next:** Add your 5 mini apps to modules/ folder
