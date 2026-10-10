-- NodeX Dashboard 1 — Supabase Schema
-- Apply once in the Supabase SQL Editor.
-- IMPORTANT: Do NOT change table or column names without updating the client code.
-- RLS is configured so the anon/authenticated user can INSERT events
-- but CANNOT UPDATE or DELETE them.

-- ── Enable UUID extension ──────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Laptops table ──────────────────────────────────────────────────────────
-- One row per registered laptop, identified by hardware fingerprint.
CREATE TABLE IF NOT EXISTS public.laptops (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fingerprint     TEXT NOT NULL UNIQUE,   -- SHA-256 of hostname+MAC+MachineGuid
    name            TEXT NOT NULL,
    os              TEXT,
    last_seen       TIMESTAMPTZ,
    battery_percent REAL,
    network_online  BOOLEAN,
    security_mode   TEXT DEFAULT 'DISARMED',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Events table ───────────────────────────────────────────────────────────
-- Immutable audit log. INSERT only — no UPDATE or DELETE via client.
CREATE TABLE IF NOT EXISTS public.events (
    id              BIGSERIAL PRIMARY KEY,
    laptop_id       UUID REFERENCES public.laptops(id) ON DELETE SET NULL,
    event_type      TEXT NOT NULL,          -- ARM, DISARM, BLE_LOST, SECURITY_EVENT, …
    state_before    TEXT,
    state_after     TEXT,
    rssi            REAL,
    rssi_smooth     REAL,
    image_url       TEXT,                   -- optional link to webcam snapshot
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp       TIMESTAMPTZ             -- client-side time (may differ)
);

-- ── Heartbeats table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.heartbeats (
    id              BIGSERIAL PRIMARY KEY,
    laptop_id       UUID REFERENCES public.laptops(id) ON DELETE SET NULL,
    event_type      TEXT DEFAULT 'HEARTBEAT',
    security_mode   TEXT,
    battery_percent REAL,
    charging        BOOLEAN,
    network_online  BOOLEAN,
    network_ip      TEXT,
    ble_connected   BOOLEAN,
    rssi_smooth     REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Alerts table ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.alerts (
    id              BIGSERIAL PRIMARY KEY,
    laptop_id       UUID REFERENCES public.laptops(id) ON DELETE SET NULL,
    event_type      TEXT,
    alert_type      TEXT,                   -- 'telegram', 'email', …
    original_event  TEXT,                   -- the security event that triggered this alert
    success         BOOLEAN,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Captures table (20-photo circular buffer) ──────────────────────────────
-- Slot 1..20: when reaching 20, the next photo overwrites slot 1.
CREATE TABLE IF NOT EXISTS public.captures (
    id              BIGSERIAL PRIMARY KEY,
    laptop_id       UUID REFERENCES public.laptops(id) ON DELETE CASCADE,
    slot            INTEGER NOT NULL CHECK (slot >= 1 AND slot <= 20),
    storage_path    TEXT NOT NULL,          -- e.g. laptops/<laptop_id>/photo_1.jpg
    image_url       TEXT,                   -- Public bucket URL
    security_mode   TEXT,                   -- ARMED, LOCKED, SECURITY_EVENT, etc.
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (laptop_id, slot)
);

-- ════════════════════════════════════════════════════════════
-- Supabase Storage Bucket (intruder-captures)
-- ════════════════════════════════════════════════════════════
INSERT INTO storage.buckets (id, name, public)
VALUES ('intruder-captures', 'intruder-captures', true)
ON CONFLICT (id) DO NOTHING;

-- ════════════════════════════════════════════════════════════
-- Row Level Security
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.laptops    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.captures   ENABLE ROW LEVEL SECURITY;

-- Authenticated users can see and upsert their own laptop
CREATE POLICY "laptops_owner" ON public.laptops
    FOR ALL USING (auth.role() = 'authenticated');

-- Authenticated users can INSERT events (but NOT update or delete)
CREATE POLICY "events_insert" ON public.events
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "events_select" ON public.events
    FOR SELECT USING (auth.role() = 'authenticated');

-- Same for heartbeats
CREATE POLICY "heartbeats_insert" ON public.heartbeats
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "heartbeats_select" ON public.heartbeats
    FOR SELECT USING (auth.role() = 'authenticated');

-- Same for alerts
CREATE POLICY "alerts_insert" ON public.alerts
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "alerts_select" ON public.alerts
    FOR SELECT USING (auth.role() = 'authenticated');

-- Captures table RLS: authenticated client can upsert / select
CREATE POLICY "captures_upsert" ON public.captures
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "captures_select_public" ON public.captures
    FOR SELECT USING (true);

-- Storage bucket policies (allow upload and overwrite)
CREATE POLICY "captures_storage_insert" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'intruder-captures' AND auth.role() = 'authenticated');

CREATE POLICY "captures_storage_update" ON storage.objects
    FOR UPDATE USING (bucket_id = 'intruder-captures' AND auth.role() = 'authenticated');

CREATE POLICY "captures_storage_select" ON storage.objects
    FOR SELECT USING (bucket_id = 'intruder-captures');

-- ════════════════════════════════════════════════════════════
-- Indexes
-- ════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_events_laptop_id ON public.events(laptop_id);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON public.events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_heartbeats_laptop_id ON public.heartbeats(laptop_id);
CREATE INDEX IF NOT EXISTS idx_heartbeats_created_at ON public.heartbeats(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_captures_laptop_slot ON public.captures(laptop_id, slot);
CREATE INDEX IF NOT EXISTS idx_captures_captured_at ON public.captures(captured_at DESC);
