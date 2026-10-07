-- NodeX: Add Laptop Hardware Telemetry Columns & Security Images Bucket
-- Run this in your Supabase SQL Editor to support detailed laptop hardware & security-images bucket

-- 1. Extend laptops table with hardware & location columns
ALTER TABLE public.laptops
    ADD COLUMN IF NOT EXISTS location JSONB,
    ADD COLUMN IF NOT EXISTS charging BOOLEAN,
    ADD COLUMN IF NOT EXISTS storage_total_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_used_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_free_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS ram_total_gb REAL,
    ADD COLUMN IF NOT EXISTS ram_used_gb REAL,
    ADD COLUMN IF NOT EXISTS ram_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS cpu_model TEXT,
    ADD COLUMN IF NOT EXISTS cpu_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS gpu_model TEXT,
    ADD COLUMN IF NOT EXISTS gpu_vram_gb REAL,
    ADD COLUMN IF NOT EXISTS gpu_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS display_info TEXT,
    ADD COLUMN IF NOT EXISTS system_specs JSONB;

-- 2. Extend heartbeats table for periodic telemetry snapshots
ALTER TABLE public.heartbeats
    ADD COLUMN IF NOT EXISTS location JSONB,
    ADD COLUMN IF NOT EXISTS storage_total_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_used_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_free_gb REAL,
    ADD COLUMN IF NOT EXISTS storage_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS ram_total_gb REAL,
    ADD COLUMN IF NOT EXISTS ram_used_gb REAL,
    ADD COLUMN IF NOT EXISTS ram_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS cpu_model TEXT,
    ADD COLUMN IF NOT EXISTS cpu_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS gpu_model TEXT,
    ADD COLUMN IF NOT EXISTS gpu_vram_gb REAL,
    ADD COLUMN IF NOT EXISTS gpu_usage_pct REAL,
    ADD COLUMN IF NOT EXISTS display_info TEXT,
    ADD COLUMN IF NOT EXISTS system_specs JSONB;

-- 3. Ensure security-images storage bucket exists
INSERT INTO storage.buckets (id, name, public)
VALUES ('security-images', 'security-images', true)
ON CONFLICT (id) DO NOTHING;

-- 4. RLS policies for security-images bucket
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'security_images_select') THEN
        CREATE POLICY "security_images_select" ON storage.objects FOR SELECT USING (bucket_id = 'security-images');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'security_images_insert') THEN
        CREATE POLICY "security_images_insert" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'security-images');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'storage' AND tablename = 'objects' AND policyname = 'security_images_update') THEN
        CREATE POLICY "security_images_update" ON storage.objects FOR UPDATE USING (bucket_id = 'security-images');
    END IF;
END $$;
