// Supabase client and strictly read-only query helpers for NodeX Dashboard 2
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

export const isConfigured = Boolean(
  supabaseUrl &&
  supabaseAnonKey &&
  supabaseUrl !== 'https://your-project.supabase.co'
);

const clientUrl = isConfigured ? supabaseUrl : 'https://placeholder.supabase.co';
const clientKey = isConfigured ? supabaseAnonKey : 'placeholder-anon-key';

export const supabase = createClient(clientUrl, clientKey, {
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
