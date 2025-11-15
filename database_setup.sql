-- Database Setup SQL for b2c_master_app
-- Run this in Supabase SQL Editor to create the user_details view
-- This view joins user_profiles with auth.users to include email addresses

-- ============================================================================
-- CREATE user_details VIEW
-- ============================================================================
-- This view combines user_profiles with auth.users to provide email addresses
-- Without this view, email addresses will show as "Unknown" in the user list

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

-- Grant SELECT permission to authenticated users
GRANT SELECT ON public.user_details TO authenticated;

-- Grant SELECT permission to service role (for admin operations)
GRANT SELECT ON public.user_details TO service_role;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Run this to verify the view was created correctly:
-- SELECT * FROM public.user_details;

-- You should see all users with their email addresses populated
