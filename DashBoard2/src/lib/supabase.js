// Supabase client and strictly read-only query helpers for NodeX Dashboard 2
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

export const isConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});

export async function getLaptops() {
  const { data, error } = await supabase
    .from('laptops')
    .select('*')
    .order('last_seen', { ascending: false });
  if (error) throw error;
  return data || [];
}

export async function getLatestHeartbeat(laptopId) {
  let query = supabase.from('heartbeats').select('*').order('created_at', { ascending: false }).limit(1);
  if (laptopId) query = query.eq('laptop_id', laptopId);
  const { data, error } = await query;
  if (error) throw error;
  return data?.[0] || null;
}

export async function getEvents({ page = 1, pageSize = 25, eventType, laptopId, search } = {}) {
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  let query = supabase
    .from('events')
    .select('*, laptops(name, os)', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(from, to);

  if (eventType && eventType !== 'ALL') {
    query = query.eq('event_type', eventType);
  }
  if (laptopId && laptopId !== 'ALL') {
    query = query.eq('laptop_id', laptopId);
  }
  if (search) {
    query = query.or(`event_type.ilike.%${search}%,state_before.ilike.%${search}%,state_after.ilike.%${search}%`);
  }

  const { data, count, error } = await query;
  if (error) throw error;
  return { events: data || [], totalCount: count || 0 };
}

export async function getRecentEvents(limit = 5) {
  const { data, error } = await supabase
    .from('events')
    .select('*, laptops(name)')
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data || [];
}

export async function getCaptures({ limit = 20, laptopId } = {}) {
  let query = supabase
    .from('captures')
    .select('*, laptops(name)')
    .order('captured_at', { ascending: false })
    .limit(limit);

  if (laptopId && laptopId !== 'ALL') {
    query = query.eq('laptop_id', laptopId);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

export async function getSignedPhotoUrl(storagePath, expiresIn = 300) {
  if (!storagePath) return null;
  const cleanPath = storagePath
    .replace(/^security-images\//, '')
    .replace(/^intruder-captures\//, '');

  const { data: secData, error: secErr } = await supabase.storage
    .from('security-images')
    .createSignedUrl(cleanPath, expiresIn);

  if (!secErr && secData?.signedUrl) return secData.signedUrl;

  const { data: intData, error: intErr } = await supabase.storage
    .from('intruder-captures')
    .createSignedUrl(cleanPath, expiresIn);

  if (!intErr && intData?.signedUrl) return intData.signedUrl;

  const { data: pubSec } = supabase.storage.from('security-images').getPublicUrl(cleanPath);
  if (pubSec?.publicUrl) return pubSec.publicUrl;

  const { data: pubInt } = supabase.storage.from('intruder-captures').getPublicUrl(cleanPath);
  return pubInt?.publicUrl || null;
}

export async function getAlerts({ limit = 50, laptopId } = {}) {
  let query = supabase
    .from('alerts')
    .select('*, laptops(name)')
    .order('created_at', { ascending: false })
    .limit(limit);

  if (laptopId && laptopId !== 'ALL') {
    query = query.eq('laptop_id', laptopId);
  }

  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

export async function getEventStats() {
  const { data, error } = await supabase
    .from('events')
    .select('id, event_type, created_at, rssi_smooth');
  if (error) throw error;
  return data || [];
}

export async function getLocations({ limit = 150, laptopId } = {}) {
  const results = [];
  const seenKeys = new Set();

  // 1. Try dedicated 'locations' table first
  try {
    let query = supabase
      .from('locations')
      .select('*, laptops(name, os)')
      .order('created_at', { ascending: false })
      .limit(limit);

    if (laptopId && laptopId !== 'ALL') {
      query = query.eq('laptop_id', laptopId);
    }

    const { data, error } = await query;
    if (!error && Array.isArray(data)) {
      data.forEach((row) => {
        if (row.latitude != null && row.longitude != null) {
          const key = `${row.laptop_id}-${row.created_at}-${row.latitude}-${row.longitude}`;
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            results.push({
              id: row.id,
              laptop_id: row.laptop_id,
              latitude: Number(row.latitude),
              longitude: Number(row.longitude),
              accuracy: row.accuracy != null ? Number(row.accuracy) : null,
              altitude: row.altitude != null ? Number(row.altitude) : null,
              source: row.source || 'winrt',
              city: row.city || null,
              region: row.region || null,
              country: row.country || null,
              country_code: row.country_code || null,
              ip: row.ip || null,
              sync_event: row.sync_event || 'PERIODIC_SYNC',
              image_url: row.image_url || null,
              metadata: row.metadata || {},
              created_at: row.created_at,
              timestamp: row.timestamp || row.created_at,
              laptops: row.laptops,
            });
          }
        }
      });
    }
  } catch (err) {
    console.debug('Locations table read note:', err);
  }

  // 2. Query 'heartbeats' table for historical records containing location JSON
  try {
    let hbQuery = supabase
      .from('heartbeats')
      .select('id, laptop_id, event_type, created_at, location, laptops(name, os)')
      .not('location', 'is', null)
      .order('created_at', { ascending: false })
      .limit(limit);

    if (laptopId && laptopId !== 'ALL') {
      hbQuery = hbQuery.eq('laptop_id', laptopId);
    }

    const { data: hbData, error: hbErr } = await hbQuery;
    if (!hbErr && Array.isArray(hbData)) {
      hbData.forEach((row) => {
        const loc = row.location;
        const lat = loc?.latitude ?? loc?.lat;
        const lon = loc?.longitude ?? loc?.lon ?? loc?.lng;
        if (lat != null && lon != null) {
          const key = `${row.laptop_id}-${row.created_at}-${lat}-${lon}`;
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            results.push({
              id: `hb-${row.id}`,
              laptop_id: row.laptop_id,
              latitude: Number(lat),
              longitude: Number(lon),
              accuracy: loc.accuracy != null ? Number(loc.accuracy) : null,
              altitude: loc.altitude != null ? Number(loc.altitude) : null,
              source: loc.source || 'heartbeat',
              city: loc.city || null,
              region: loc.region || null,
              country: loc.country || loc.country_name || null,
              country_code: loc.country_code || null,
              ip: loc.ip || null,
              sync_event: row.event_type || 'HEARTBEAT',
              image_url: loc.image_url || null,
              metadata: loc.metadata || {},
              created_at: row.created_at,
              timestamp: loc.timestamp || row.created_at,
              laptops: row.laptops,
            });
          }
        }
      });
    }
  } catch (err2) {
    console.debug('Heartbeats location fallback note:', err2);
  }

  // Sort chronological order (newest first for list, oldest to newest for map trajectory)
  results.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  return results;
}

