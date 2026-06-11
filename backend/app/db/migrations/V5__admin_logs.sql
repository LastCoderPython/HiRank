-- Migration V5: Admin event log table
-- ⚠️  CONSOLIDATED: The `admin_logs` table is now defined in V1__base_schema.sql.
-- This file is kept for backward compatibility with existing databases.

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
