-- Migration V3: Onboarding + engagement data columns
-- ⚠️  CONSOLIDATED: All columns and indexes from this migration are now
-- defined in V1__base_schema.sql. This file is kept for backward
-- compatibility with existing databases. All statements are idempotent.

-- ─── New columns on profiles ─────────────────────────────────────────
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS onboarding_complete   BOOLEAN  DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS exam                  TEXT,
  ADD COLUMN IF NOT EXISTS rank                  INTEGER,
  ADD COLUMN IF NOT EXISTS percentile            NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS category              TEXT,
  ADD COLUMN IF NOT EXISTS home_state            TEXT,
  ADD COLUMN IF NOT EXISTS branch_preferences    TEXT[],
  ADD COLUMN IF NOT EXISTS whatsapp_number       TEXT,
  ADD COLUMN IF NOT EXISTS fingerprint_id        TEXT;

-- ─── Analytics indexes ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_profiles_exam        ON public.profiles(exam);
CREATE INDEX IF NOT EXISTS idx_profiles_category    ON public.profiles(category);
CREATE INDEX IF NOT EXISTS idx_profiles_home_state  ON public.profiles(home_state);
CREATE INDEX IF NOT EXISTS idx_profiles_fingerprint ON public.profiles(fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_profiles_onboarding  ON public.profiles(onboarding_complete);

-- ─── Update handle_new_user trigger ──────────────────────────────────
-- New users start with onboarding_complete = false
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, avatar_url, onboarding_complete)
    VALUES (
        NEW.id,
        COALESCE(NEW.email, ''),
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            split_part(COALESCE(NEW.email, 'user'), '@', 1)
        ),
        NEW.raw_user_meta_data->>'avatar_url',
        FALSE
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
