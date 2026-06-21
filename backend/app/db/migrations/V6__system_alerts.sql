-- V6: System Alerts table
-- Stores admin-authored alerts that are injected into the LLM system prompt.
-- Only one alert should be active at a time; set_active_alert() enforces this.

CREATE TABLE IF NOT EXISTS public.system_alerts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for the common "get the active alert" query
CREATE INDEX IF NOT EXISTS idx_system_alerts_active ON public.system_alerts (is_active)
    WHERE is_active = TRUE;

-- Row-Level Security: only service role can read/write
ALTER TABLE public.system_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON public.system_alerts
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);
