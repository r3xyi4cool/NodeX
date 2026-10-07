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
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card font-mono"
          >
            <option value="ALL">All Modes</option>
            <option value="ARMED">ARMED</option>
            <option value="LOCKED">LOCKED</option>
            <option value="SECURITY_EVENT">SECURITY_EVENT</option>
          </select>
          <button
            onClick={loadData}
            aria-label="Refresh captures"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card text-slate-500 hover:text-cyan-500"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 p-3 rounded-xl border border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs font-mono">
        <Info className="w-4 h-4 shrink-0" />
        <span>20-slot circular ring buffer: Slot 21 automatically overwrites Slot 1 locally and in the 'security-images' Supabase Storage bucket.</span>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-video rounded-xl bg-slate-200 dark:bg-slate-800 animate-pulse" />
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
              className="group relative rounded-xl overflow-hidden border border-slate-200 dark:border-nodex-border bg-black aspect-video cursor-pointer hover:border-cyan-500/50 transition-all shadow-md"
            >
              <img src={item.url} alt={`Slot ${item.slot}`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-90 p-3 flex flex-col justify-end text-xs font-mono text-white">
                <div className="flex items-center justify-between">
                  <span className="font-bold">Slot {item.slot} / 20</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/20">{item.security_mode}</span>
                </div>
                <span className="text-[10px] text-slate-300 mt-0.5">{new Date(item.captured_at).toLocaleString()}</span>
              </div>
              <div className="absolute top-2 right-2 p-1 rounded-md bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity">
                <ZoomIn className="w-4 h-4" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
