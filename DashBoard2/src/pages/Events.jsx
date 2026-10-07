// Paginated security events table with type filters, search, and detail inspection side panel
import React, { useState, useEffect } from 'react';
import { Search, ChevronLeft, ChevronRight, Activity, Filter } from 'lucide-react';
import { Table, TableRow } from '../components/Table';
import { Badge } from '../components/Badge';
import { TableSkeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { EventDetailPanel } from '../components/EventDetailPanel';
import { getEvents, getLaptops } from '../lib/supabase';

const EVENT_TYPES = ['ALL', 'ARM', 'DISARM', 'BLE_LOST', 'TOKEN_RECOVERED', 'SECURITY_EVENT', 'MANUAL_TEST'];

export function Events() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [events, setEvents] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [eventType, setEventType] = useState('ALL');
  const [selectedEvent, setSelectedEvent] = useState(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getEvents({ page, pageSize: 25, eventType, search });
      setEvents(res.events);
      setTotalCount(res.totalCount);
    } catch (err) {
      setError(err.message || 'Failed to fetch security events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [page, eventType, search]);

  const totalPages = Math.max(Math.ceil(totalCount / 25), 1);

  const columns = [
    { header: 'ID', className: 'w-16' },
    { header: 'Event Type' },
    { header: 'Transition' },
    { header: 'Signal (RSSI)' },
    { header: 'Laptop' },
    { header: 'Logged Time (UTC)', align: 'right' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-white font-sans">Security Events Audit Log</h2>
          <p className="text-xs text-[#c9d1de]">Read-only immutable log from Supabase</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3.5 top-3 text-[#7c8ba1]" />
            <input
              type="text"
              placeholder="Search events..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-9 pr-4 py-2 text-xs rounded-full border border-white/15 bg-white/[0.04] text-white placeholder:text-[#7c8ba1] focus:outline-none focus:border-[#006eff] focus:ring-1 focus:ring-[#006eff] transition-all"
            />
          </div>
          <select
            value={eventType}
            onChange={(e) => { setEventType(e.target.value); setPage(1); }}
            className="px-3.5 py-2 text-xs rounded-full border border-white/15 bg-[#000d26] text-white font-mono focus:outline-none focus:border-[#006eff] transition-all"
          >
            {EVENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <TableSkeleton rows={8} cols={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : events.length === 0 ? (
        <EmptyState title="No Events Found" description="Try selecting a different event type or clearing your search filter." />
      ) : (
        <>
          <Table columns={columns}>
            {events.map((ev) => (
              <TableRow key={ev.id} onClick={() => setSelectedEvent(ev)}>
                <td className="py-3.5 px-4 font-mono text-[#7c8ba1]">#{ev.id}</td>
                <td className="py-3.5 px-4"><Badge variant={ev.event_type}>{ev.event_type}</Badge></td>
                <td className="py-3.5 px-4 text-[#c9d1de]">{ev.state_before} &rarr; {ev.state_after}</td>
                <td className="py-3.5 px-4 text-white font-semibold">{ev.rssi_smooth ? `${ev.rssi_smooth} dBm` : '—'}</td>
                <td className="py-3.5 px-4 text-[#c9d1de] truncate max-w-[120px]">{ev.laptops?.name || 'Device'}</td>
                <td className="py-3.5 px-4 text-right text-[#7c8ba1]">{new Date(ev.created_at).toLocaleString()}</td>
              </TableRow>
            ))}
          </Table>

          <div className="flex items-center justify-between text-xs font-mono text-[#7c8ba1] pt-2">
            <span>Showing page {page} of {totalPages} ({totalCount} total)</span>
            <div className="flex items-center gap-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="p-2 rounded-full border border-white/15 text-[#c9d1de] hover:text-white hover:border-[#006eff] hover:bg-[#006eff]/15 disabled:opacity-30 transition-all"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="p-2 rounded-full border border-white/15 text-[#c9d1de] hover:text-white hover:border-[#006eff] hover:bg-[#006eff]/15 disabled:opacity-30 transition-all"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}

      <EventDetailPanel
        event={selectedEvent}
        isOpen={Boolean(selectedEvent)}
        onClose={() => setSelectedEvent(null)}
      />
    </div>
  );
}
