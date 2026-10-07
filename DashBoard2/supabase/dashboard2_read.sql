-- NodeX Dashboard 2 — SELECT-Only Read Access Policies
-- Run this in your Supabase SQL Editor if you need to grant explicit read-only access for authenticated users.
-- This script ONLY creates SELECT policies and NEVER grants INSERT, UPDATE, or DELETE permissions.

-- 1. Ensure RLS is enabled on all telemetry tables
ALTER TABLE IF EXISTS public.laptops    ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.alerts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.captures   ENABLE ROW LEVEL SECURITY;

-- 2. Idempotent SELECT-only policy for laptops
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'laptops' AND policyname = 'dashboard2_laptops_select'
    ) THEN
        CREATE POLICY "dashboard2_laptops_select" ON public.laptops
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 3. Idempotent SELECT-only policy for security events audit trail
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'events' AND policyname = 'dashboard2_events_select'
    ) THEN
        CREATE POLICY "dashboard2_events_select" ON public.events
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 4. Idempotent SELECT-only policy for periodic device heartbeats
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'heartbeats' AND policyname = 'dashboard2_heartbeats_select'
    ) THEN
        CREATE POLICY "dashboard2_heartbeats_select" ON public.heartbeats
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 5. Idempotent SELECT-only policy for emergency alert dispatch logs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'alerts' AND policyname = 'dashboard2_alerts_select'
    ) THEN
        CREATE POLICY "dashboard2_alerts_select" ON public.alerts
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 6. Idempotent SELECT-only policy for webcam captures metadata
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'captures' AND policyname = 'dashboard2_captures_select'
    ) THEN
        CREATE POLICY "dashboard2_captures_select" ON public.captures
            FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 7. Idempotent SELECT-only policy for private storage bucket objects (signed URLs)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'dashboard2_storage_select'
    ) THEN
        CREATE POLICY "dashboard2_storage_select" ON storage.objects
            FOR SELECT TO authenticated USING (bucket_id = 'intruder-captures');
    END IF;
END $$;
