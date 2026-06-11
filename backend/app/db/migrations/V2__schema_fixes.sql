-- V2 Migration: Schema fixes for RankRoute
-- Run this after V1 (schema.sql) when migrating to new Supabase instance

-- 1. Add missing phone column to profiles
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS phone TEXT;
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON public.profiles(phone);

-- 2. Add missing index for temp_messages ordering
CREATE INDEX IF NOT EXISTS idx_temp_messages_created_at ON public.temp_messages(created_at);

-- 3. Add DELETE RLS policy for messages
CREATE POLICY "Users can delete messages in own chats" ON public.messages
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id AND chats.user_id = auth.uid()
        )
    );

-- 4. Add UPDATE RLS policy for messages (future-proofing)
CREATE POLICY "Users can update messages in own chats" ON public.messages
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE chats.id = messages.chat_id AND chats.user_id = auth.uid()
        )
    );

-- 5. Fix SECURITY DEFINER function: add search_path
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. Optionally: switch from uuid-ossp to pgcrypto
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- Then update DEFAULT uuid_generate_v4() to DEFAULT gen_random_uuid() in schema.sql
