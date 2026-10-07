// Large side panel displaying complete security event audit details and linked telemetry
import React, { useEffect } from 'react';
import { X, Shield, Activity, Clock, Laptop, Wifi, MapPin, Camera } from 'lucide-react';
import { Badge } from './Badge';

export function EventDetailPanel({ event, isOpen, onClose, onOpenPhoto }) {
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  if (!isOpen || !event) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-label="Event Details">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-[#000511]/95 backdrop-blur-2xl border-l border-white/10 p-6 shadow-[0_0_50px_rgba(0,0,0,0.8)] flex flex-col justify-between overflow-y-auto">
          <div className="space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <Shield className="w-5 h-5 text-[#006eff]" />
                <h3 className="text-sm font-bold text-white">Event #{event.id} Details</h3>
              </div>
              <button onClick={onClose} aria-label="Close details" className="p-1.5 rounded-full border border-white/15 text-[#c9d1de] hover:text-white hover:bg-white/10 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#7c8ba1]">Classification</span>
              <div className="mt-1 flex items-center gap-2">
                <Badge variant={event.event_type} size="md">{event.event_type}</Badge>
                <span className="text-xs font-mono text-[#c9d1de]">
                  {event.state_before} &rarr; {event.state_after}
                </span>
              </div>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                <span className="text-[#7c8ba1] text-[10px] block">TIMESTAMP (UTC)</span>
                <span className="font-semibold text-white">{new Date(event.created_at).toISOString()}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                <span className="text-[#7c8ba1] text-[10px] block">LAPTOP & TOKEN</span>
                <span className="font-semibold text-white">{event.laptops?.name || 'Registered Laptop'}</span>
                <span className="text-[11px] text-[#7c8ba1] block">UUID: {event.laptop_id || 'Unknown'}</span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                  <span className="text-[#7c8ba1] text-[10px] block">RAW RSSI</span>
                  <span className="font-semibold text-white">{event.rssi ? `${event.rssi} dBm` : 'N/A'}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                  <span className="text-[#7c8ba1] text-[10px] block">SMOOTH RSSI</span>
                  <span className="font-semibold text-white">{event.rssi_smooth ? `${event.rssi_smooth} dBm` : 'N/A'}</span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                <span className="text-[#7c8ba1] text-[10px] block">NETWORK & IP</span>
                <span className="font-semibold text-white">Active (Local 127.0.0.1)</span>
              </div>

              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10">
                <span className="text-[#7c8ba1] text-[10px] block">DAEMON RESPONSE</span>
                <span className="font-semibold text-white">
                  {event.event_type === 'SECURITY_EVENT' ? 'Workstation Locked via LockWorkStation' : 'State Transition Logged'}
                </span>
              </div>
            </div>

            {event.image_url && (
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#7c8ba1] block mb-2">Linked Snapshot</span>
                <div className="relative rounded-2xl overflow-hidden border border-white/10 cursor-pointer aspect-video bg-black hover:border-[#006eff]/50 transition-all" onClick={() => onOpenPhoto && onOpenPhoto(event.image_url)}>
                  <img src={event.image_url} alt="Event snap" className="w-full h-full object-cover" />
                  <div className="absolute inset-0 bg-black/40 flex items-center justify-center text-white text-xs font-mono">Click to view</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
