# Database Setup Instructions

## Issue: Email Addresses Showing as "Unknown"

If email addresses are showing as "Unknown" in the User Management > All Users tab, you need to create the `user_details` view in your Supabase database.

## Solution: Create user_details View

### Step 1: Open Supabase SQL Editor

1. Go to your Supabase project dashboard
2. Click on **SQL Editor** in the left sidebar
3. Click **New Query**

### Step 2: Run the SQL Script

Copy and paste the entire contents of `database_setup.sql` into the SQL editor and click **Run**.

Alternatively, copy this SQL directly:

```sql
CREATE OR REPLACE VIEW public.user_details AS
SELECT
    up.id,
    au.email,
    up.full_name,
    up.role_id,
    up.is_active,
    up.created_at,
    up.updated_at
FROM
    public.user_profiles up
LEFT JOIN
    auth.users au ON up.id = au.id;

GRANT SELECT ON public.user_details TO authenticated;
GRANT SELECT ON public.user_details TO service_role;
```

### Step 3: Verify the View

Run this query to verify the view was created successfully:

```sql
SELECT * FROM public.user_details;
```

You should see all your users with their email addresses properly populated.

### Step 4: Clear Cache in Your App

After creating the view:
1. Go to your Streamlit app
2. Click on the hamburger menu (☰) in the top right
3. Select **Clear cache**
4. Navigate to User Management > All Users
5. Email addresses should now display correctly

## Troubleshooting

### Error: "permission denied for schema auth"

If you get a permission error when creating the view, make sure you're logged in as the database owner or have sufficient privileges. You may need to run this from the Supabase SQL Editor (not from your application).

### Emails Still Showing as "Unknown"

1. Verify the view exists:
   ```sql
   SELECT table_name FROM information_schema.views WHERE table_name = 'user_details';
   ```

2. Check if there are users in auth.users:
   ```sql
   SELECT id, email FROM auth.users LIMIT 5;
   ```

3. Check the application logs for error messages (terminal where Streamlit is running)

## User Creation Issues

If you're getting errors when creating new users (e.g., "User not allowed"), this is a separate issue related to SMTP configuration:

1. Go to Supabase Dashboard → **Authentication** → **Email Templates** → **SMTP Settings**
2. Configure custom SMTP (Gmail, Zoho, etc.)
3. Test the SMTP connection
4. Try creating a user again

Note: Password reset emails working does NOT mean SMTP is configured for user creation. They may use different settings.
