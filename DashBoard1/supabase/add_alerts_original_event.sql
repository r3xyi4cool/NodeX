-- NodeX: Add original_event column to alerts table
-- Run this in your Supabase SQL Editor.
-- This column records which security event triggered each alert (e.g. SECURITY_EVENT, MANUAL_TEST).

ALTER TABLE public.alerts
    ADD COLUMN IF NOT EXISTS original_event TEXT;
