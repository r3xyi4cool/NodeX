-- NodeX: Add Locations Table for Historical Geo-Tracking & OpenStreetMap Viewer
-- Run this script in your Supabase SQL Editor to create the locations history table and configure RLS.

CREATE TABLE IF NOT EXISTS public.locations (
    id              BIGSERIAL PRIMARY KEY,
    laptop_id       UUID REFERENCES public.laptops(id) ON DELETE CASCADE,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    accuracy        REAL,
    altitude        REAL,
    source          TEXT DEFAULT 'winrt',         -- 'winrt', 'ip-api', 'ipapi.co', 'manual'
    city            TEXT,
    region          TEXT,
    country         TEXT,
    country_code    TEXT,
    ip              TEXT,
    sync_event      TEXT DEFAULT 'PERIODIC_SYNC', -- 'PERIODIC_SYNC', 'MANUAL_SEND', 'DEMO_SYNC'
    image_url       TEXT,                         -- Associated surveillance snapshot if taken alongside
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;

-- Allow insert by authenticated users or anon (client synchronization)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'locations' AND policyname = 'locations_insert_policy'
    ) THEN
        CREATE POLICY "locations_insert_policy" ON public.locations
            FOR INSERT WITH CHECK (true);
    END IF;
END $$;

-- Allow read access for authenticated users (Dashboard 2 & Dashboard 1)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'locations' AND policyname = 'locations_select_policy'
    ) THEN
        CREATE POLICY "locations_select_policy" ON public.locations
            FOR SELECT USING (true);
    END IF;
END $$;

-- Indexes for efficient timeline queries & foreign key lookups
CREATE INDEX IF NOT EXISTS idx_locations_laptop_id ON public.locations(laptop_id);
CREATE INDEX IF NOT EXISTS idx_locations_created_at ON public.locations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_locations_timestamp ON public.locations(timestamp DESC);
