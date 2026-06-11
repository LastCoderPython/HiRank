-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- Note: gen_random_uuid() from pgcrypto is preferred over uuid-ossp for PG 13+
-- Kept for backward compatibility; can be dropped if nothing else depends on it
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Profiles table (stores user data from auth + onboarding)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    name TEXT,
    avatar_url TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin', 'moderator')),
    -- Onboarding & engagement fields
    onboarding_complete BOOLEAN DEFAULT FALSE,
    exam TEXT,                    -- 'JEE_MAIN','JEE_ADV','NEET','CEE','OTHER'
    rank INTEGER,                 -- AIR or state rank
    percentile NUMERIC(5,2),     -- e.g. 97.45
    category TEXT,               -- 'General','OBC','SC','ST','EWS'
    home_state TEXT,             -- collected progressively via Settings
    branch_preferences TEXT[],   -- collected progressively via Settings
    whatsapp_number TEXT,        -- voluntarily provided
    fingerprint_id TEXT,         -- FingerprintJS Visitor ID for anti-abuse
    -- Extended profile fields (C-08 fix)
    budget_range JSONB,          -- e.g. {"min": 50000, "max": 200000}
    hostel_required BOOLEAN,     -- whether user needs hostel
    location_preference TEXT,    -- preferred college location
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chats table (for authenticated users)
CREATE TABLE IF NOT EXISTS public.chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table (for authenticated users)
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Temporary chats table (for non-authenticated users)
CREATE TABLE IF NOT EXISTS public.temp_chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT 'Temporary Chat',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Temporary messages table (for non-authenticated users)
CREATE TABLE IF NOT EXISTS public.temp_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL REFERENCES public.temp_chats(session_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON public.chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON public.chats(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON public.messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);
CREATE INDEX IF NOT EXISTS idx_temp_chats_session_id ON public.temp_chats(session_id);
CREATE INDEX IF NOT EXISTS idx_temp_messages_session_id ON public.temp_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_temp_messages_created_at ON public.temp_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON public.profiles(phone);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_profiles_exam ON public.profiles(exam);
CREATE INDEX IF NOT EXISTS idx_profiles_category ON public.profiles(category);
CREATE INDEX IF NOT EXISTS idx_profiles_home_state ON public.profiles(home_state);
CREATE INDEX IF NOT EXISTS idx_profiles_fingerprint ON public.profiles(fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_profiles_onboarding ON public.profiles(onboarding_complete);

-- Enable Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.temp_chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.temp_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for profiles (users can only read/write their own profile)
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- RLS Policies for chats (users can only access their own chats)
CREATE POLICY "Users can view own chats" ON public.chats
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own chats" ON public.chats
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own chats" ON public.chats
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own chats" ON public.chats
    FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for messages (users can only access messages in their chats)
CREATE POLICY "Users can view messages in own chats" ON public.messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.chats 
            WHERE chats.id = messages.chat_id 
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages in own chats" ON public.messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.chats 
            WHERE chats.id = messages.chat_id 
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update messages in own chats" ON public.messages
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.chats 
            WHERE chats.id = messages.chat_id 
            AND chats.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages in own chats" ON public.messages
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.chats 
            WHERE chats.id = messages.chat_id 
            AND chats.user_id = auth.uid()
        )
    );

-- For temp tables, we allow all since they use session_id instead of auth
CREATE POLICY "Allow all temp chats" ON public.temp_chats
    FOR ALL USING (true);

CREATE POLICY "Allow all temp messages" ON public.temp_messages
    FOR ALL USING (true);

-- Function to automatically create profile on user signup
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

-- Trigger to create profile on signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS update_chats_updated_at ON public.chats;
CREATE TRIGGER update_chats_updated_at
    BEFORE UPDATE ON public.chats
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS update_temp_chats_updated_at ON public.temp_chats;
CREATE TRIGGER update_temp_chats_updated_at
    BEFORE UPDATE ON public.temp_chats
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- Admin event log (accessed via service_role key, no RLS needed)
CREATE TABLE IF NOT EXISTS public.admin_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    actor_id    TEXT,
    actor_role  TEXT NOT NULL DEFAULT 'system',
    summary     TEXT NOT NULL,
    details     JSONB,
    source      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_event_type ON public.admin_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_admin_logs_severity   ON public.admin_logs(severity);
CREATE INDEX IF NOT EXISTS idx_admin_logs_source     ON public.admin_logs(source);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created_at ON public.admin_logs(created_at DESC);
