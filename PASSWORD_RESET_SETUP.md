# Password Reset Setup Guide

This guide explains how to configure password reset functionality to work correctly with THIS specific app.

## Problem: Password Reset Redirecting to Wrong App

If you have multiple Streamlit apps using the same Supabase project, password reset links may redirect to the wrong app. This happens because Supabase needs to know which app URL to use for each password reset request.

## Solution: Configure Supabase Redirect URLs

Follow these steps to ensure password resets redirect to THIS app specifically:

---

## Step 1: Get Your App URL

### For Streamlit Cloud:
Your app URL will be in this format:
```
https://[your-app-name]--[your-username].streamlit.app
```

Example:
```
https://b2c-master-app--yourusername.streamlit.app
```

### For Local Development:
```
http://localhost:8501
```

### For Custom Domain:
```
https://your-custom-domain.com
```

---

## Step 2: Configure Supabase Dashboard

1. **Log in to your Supabase Dashboard**
   - Go to: https://app.supabase.com
   - Select your project

2. **Navigate to Authentication Settings**
   - Click **Authentication** in the left sidebar
   - Click **URL Configuration**

3. **Set Site URL** (IMPORTANT!)
   - Find the "Site URL" field
   - Enter YOUR app's URL (from Step 1):
     ```
     https://b2c-master-app--yourusername.streamlit.app
     ```
   - This is the default URL Supabase will use for redirects

4. **Configure Redirect URLs** (Multiple Apps Support)
   - Find the "Redirect URLs" section
   - Add ALL your app URLs (one per line):
     ```
     https://b2c-master-app--yourusername.streamlit.app/**
     http://localhost:8501/**
     ```
   - The `/**` wildcard allows all paths under that domain
   - If you have other apps, add them here too:
     ```
     https://b2c-master-app--yourusername.streamlit.app/**
     https://other-app--yourusername.streamlit.app/**
     http://localhost:8501/**
     ```

5. **Configure Email Templates** (Optional but Recommended)
   - Click **Email Templates** in the left sidebar
   - Select **Reset Password** template
   - Update the reset link to point to YOUR app's redirect.html:
     ```html
     <a href="{{ .SiteURL }}/static/redirect.html#access_token={{ .Token }}&type=recovery">
       Reset Password
     </a>
     ```
   - Make sure `{{ .SiteURL }}` matches YOUR app URL

6. **Save Changes**
   - Click **Save** at the bottom of the page

---

## Step 3: Update redirect.html (If Needed)

If you want to hardcode your app URL (most reliable for production), update `/static/redirect.html`:

1. Open `static/redirect.html`

2. Find this line (around line 17):
   ```javascript
   const APP_URL = window.location.origin; // Use current origin by default
   ```

3. Replace it with your specific app URL:
   ```javascript
   const APP_URL = "https://b2c-master-app--yourusername.streamlit.app";
   ```

4. This ensures the redirect ALWAYS goes to THIS app, not any other app

---

## Step 4: Test the Password Reset Flow

1. **Request Password Reset**
   - Go to your app's login page
   - Click "Forgot Password?"
   - Enter your email
   - Click "Send Reset Link"

2. **Check Your Email**
   - You should receive an email from Supabase
   - Click the "Reset Password" link in the email

3. **Verify Redirect**
   - The link should open `/static/redirect.html`
   - You should see "Redirecting to password reset page..."
   - After ~1 second, you should be redirected to YOUR app (not another app!)
   - You should see the "Set New Password" page

4. **Complete Password Reset**
   - Enter your new password
   - Confirm the password
   - Click "Update Password"
   - You should see a success message
   - After 2 seconds, you'll be redirected to the login page
   - Log in with your new password

---

## Troubleshooting

### Issue: Still redirecting to wrong app

**Solution A: Check Site URL in Supabase**
- Make sure "Site URL" in Supabase matches THIS app's URL
- The Site URL is the PRIMARY redirect target

**Solution B: Hardcode APP_URL in redirect.html**
- Update `static/redirect.html` as shown in Step 3
- This overrides the automatic detection

**Solution C: Use app-specific redirect URLs**
- In Supabase Email Templates, hardcode the full redirect URL:
  ```html
  <a href="https://b2c-master-app--yourusername.streamlit.app/static/redirect.html#access_token={{ .Token }}&type=recovery">
  ```
- This ensures the email link points to THIS specific app

### Issue: redirect.html not found (404 error)

**Solution:**
- Ensure `.streamlit/config.toml` has:
  ```toml
  [server]
  enableStaticServing = true
  ```
- Ensure `static/redirect.html` exists
- Restart your Streamlit app

### Issue: Invalid or expired reset link

**Solution:**
- Password reset tokens expire after 1 hour
- Request a new password reset link
- Complete the reset within 1 hour

### Issue: Email not received

**Solution:**
- Check your spam/junk folder
- Verify email settings in Supabase Dashboard
- For development: Check Supabase logs for email delivery status

---

## Security Notes

1. **Email Enumeration Prevention**
   - The app always shows "success" when requesting password reset
   - This prevents attackers from discovering which emails exist in your system

2. **Token Expiration**
   - Reset tokens expire after 1 hour (Supabase default)
   - Tokens can only be used once

3. **Password Requirements**
   - Minimum 8 characters enforced
   - Consider adding complexity requirements in future updates

4. **HTTPS Required**
   - For production, always use HTTPS URLs
   - Password reset links contain sensitive tokens

---

## File Structure

```
b2c_master_app/
├── .streamlit/
│   └── config.toml              # Enables static file serving
├── static/
│   └── redirect.html            # Handles password reset redirect
├── auth/
│   ├── login.py                 # Login page + password reset UI
│   └── session.py               # SessionManager with reset methods
├── app.py                       # Main app with reset flow detection
└── PASSWORD_RESET_SETUP.md      # This file
```

---

## Complete Workflow

1. **Admin creates new user**
   - In User Management, admin creates account
   - User receives email (or admin informs them they're created)

2. **New user sets password**
   - User goes to login page
   - Clicks "Forgot Password?"
   - Enters their email
   - Receives password reset email

3. **User clicks email link**
   - Link points to `/static/redirect.html` with token
   - redirect.html extracts token and redirects to main app
   - Main app detects `reset_password=true` query parameter
   - Shows "Set New Password" page

4. **User enters new password**
   - Enters password twice (confirmation)
   - Password is validated (min 8 chars)
   - Supabase updates the password
   - User is redirected to login page

5. **User logs in**
   - User logs in with new self-set password
   - No temporary passwords exposed in UI!

---

## Support

If you continue to have issues with password reset redirects:

1. Double-check Supabase Site URL matches YOUR app
2. Hardcode APP_URL in redirect.html
3. Check browser console for JavaScript errors
4. Check Streamlit logs for server errors
5. Verify static files are being served correctly

For more help, contact your system administrator.
