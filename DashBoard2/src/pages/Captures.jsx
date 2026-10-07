// Responsive webcam captures gallery with signed photo URLs, ring buffer notice and date grouping
import React, { useState, useEffect } from 'react';
import { Camera, Calendar, Info, RefreshCw, ZoomIn } from 'lucide-react';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { getCaptures, getSignedPhotoUrl } from '../lib/supabase';

export function Captures({ onOpenLightbox }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [captures, setCaptures] = useState([]);
  const [filterMode, setFilterMode] = useState('ALL');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const raw = await getCaptures({ limit: 20 });
      const signed = await Promise.all(
        raw.map(async (c) => ({
          ...c,
          url: await getSignedPhotoUrl(c.storage_path, 300),
        }))
      );
      setCaptures(signed);
    } catch (err) {
      setError(err.message || 'Failed to load surveillance captures');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filtered = filterMode === 'ALL' ? captures : captures.filter((c) => c.security_mode === filterMode);

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Webcam Intruder Surveillance</h2>
          <p className="text-xs text-slate-500 dark:text-nodex-secondary">Webcam captures retrieved from security-images bucket (5 min TTL)</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filterMode}
            onChange={(e) => setFilterMode(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-full border border-slate-200 dark:border-white/10 bg-white dark:bg-[#000c24]/90 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#006eff] transition-colors font-mono"
          >
            <option value="ALL">All Modes</option>
            <option value="ARMED">ARMED</option>
            <option value="LOCKED">LOCKED</option>
            <option value="SECURITY_EVENT">SECURITY_EVENT</option>
          </select>
          <button
            onClick={loadData}
            aria-label="Refresh captures"
            className="p-2 rounded-full border border-slate-200 dark:border-white/10 bg-white dark:bg-[#000c24]/90 text-slate-500 dark:text-slate-300 hover:text-[#006eff] hover:border-[#006eff]/50 transition-all shadow-sm"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 p-3.5 rounded-2xl border border-amber-500/20 bg-amber-500/10 dark:bg-amber-500/5 backdrop-blur-md text-amber-700 dark:text-amber-400 text-xs font-mono shadow-sm">
        <Info className="w-4 h-4 shrink-0 text-amber-500" />
        <span>20-slot circular ring buffer: Slot 21 automatically overwrites Slot 1 locally and in the 'security-images' Supabase Storage bucket.</span>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-video rounded-2xl bg-slate-200 dark:bg-white/5 animate-pulse border border-slate-200/50 dark:border-white/5" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No Captures Recorded" description="Webcam photos are snapped periodically when the system is ARMED or LOCKED." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {filtered.map((item, idx) => (
            <div
              key={item.id || idx}
              onClick={() => onOpenLightbox && onOpenLightbox(filtered, idx)}
              className="group relative rounded-2xl overflow-hidden border border-slate-200 dark:border-white/10 bg-black aspect-video cursor-pointer hover:border-[#006eff]/60 hover:shadow-[0_0_20px_rgba(0,110,255,0.25)] transition-all duration-300"
            >
              <img src={item.url} alt={`Slot ${item.slot}`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" />
              <div className="absolute inset-0 bg-gradient-to-t from-[#000308]/90 via-transparent to-transparent opacity-95 p-3 flex flex-col justify-end text-xs font-mono text-white">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white tracking-wide">Slot {item.slot} / 20</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/15 backdrop-blur-md border border-white/10 text-white font-medium">{item.security_mode}</span>
                </div>
                <span className="text-[10px] text-slate-300 mt-1">{new Date(item.captured_at).toLocaleString()}</span>
              </div>
              <div className="absolute top-2.5 right-2.5 p-1.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-white opacity-0 group-hover:opacity-100 transition-opacity">
                <ZoomIn className="w-4 h-4 text-[#006eff]" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
