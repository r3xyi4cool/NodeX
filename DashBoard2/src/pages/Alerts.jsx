// Alerts audit view displaying channel dispatches, delivery statuses and error logs
import React, { useState, useEffect } from 'react';
import { Bell, CheckCircle2, AlertCircle, RefreshCw, Send } from 'lucide-react';
import { Table, TableRow } from '../components/Table';
import { Badge } from '../components/Badge';
import { TableSkeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { getAlerts } from '../lib/supabase';

export function Alerts() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [statusFilter, setStatusFilter] = useState('ALL');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getAlerts({ limit: 50 });
      setAlerts(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch alerts log');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filtered = statusFilter === 'ALL'
    ? alerts
    : statusFilter === 'SUCCESS'
    ? alerts.filter((a) => a.success)
    : alerts.filter((a) => !a.success);

  const columns = [
    { header: 'ID', className: 'w-16' },
    { header: 'Channel' },
    { header: 'Trigger Event' },
    { header: 'Delivery Status' },
    { header: 'Error Details' },
    { header: 'Dispatched Time', align: 'right' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Emergency Alerts Audit Log</h2>
          <p className="text-xs text-slate-500 dark:text-nodex-secondary">Telegram and webhook notification delivery logs</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-full border border-slate-200 dark:border-white/10 bg-white dark:bg-[#000c24]/90 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-[#006eff] transition-colors font-mono"
          >
            <option value="ALL">All Statuses</option>
            <option value="SUCCESS">Delivered</option>
            <option value="FAILED">Failed</option>
          </select>
          <button
            onClick={loadData}
            aria-label="Refresh alerts"
            className="p-2 rounded-full border border-slate-200 dark:border-white/10 bg-white dark:bg-[#000c24]/90 text-slate-500 dark:text-slate-300 hover:text-[#006eff] hover:border-[#006eff]/50 transition-all shadow-sm"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading ? (
        <TableSkeleton rows={6} cols={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={loadData} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No Alert Records" description="Alerts are dispatched when security breach events occur while armed." />
      ) : (
        <Table columns={columns}>
          {filtered.map((al) => (
            <TableRow key={al.id}>
              <td className="py-3 px-4 font-mono text-slate-400">#{al.id}</td>
              <td className="py-3 px-4 flex items-center gap-2 uppercase font-mono text-xs">
                <Send className="w-3.5 h-3.5 text-[#006eff]" />
                <span className="text-slate-200 font-semibold">{al.alert_type || 'telegram'}</span>
              </td>
              <td className="py-3 px-4"><Badge variant={al.event_type}>{al.event_type || 'SECURITY_EVENT'}</Badge></td>
              <td className="py-3 px-4 font-mono">
                {al.success ? (
                  <span className="inline-flex items-center gap-1.5 text-emerald-400 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Delivered
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-rose-400 font-medium">
                    <AlertCircle className="w-4 h-4 text-rose-400" /> Failed
                  </span>
                )}
              </td>
              <td className="py-3 px-4 font-mono text-slate-400 text-[11px] truncate max-w-[200px]">
                {al.error || 'None'}
              </td>
              <td className="py-3 px-4 text-right font-mono text-slate-400 text-xs">
                {new Date(al.created_at).toLocaleString()}
              </td>
            </TableRow>
          ))}
        </Table>
      )}
    </div>
  );
}
