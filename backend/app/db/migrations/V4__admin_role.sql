-- Migration V4: Admin role support
-- ⚠️  CONSOLIDATED: The `role` column is now defined in V1__base_schema.sql.
-- This file is kept for backward compatibility with existing databases.

-- Add role column to profiles
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user'
  CHECK (role IN ('user', 'admin', 'moderator'));

CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- Bootstrap initial admin (set your email after running)
-- UPDATE public.profiles SET role = 'admin' WHERE email = 'your@email.com';
