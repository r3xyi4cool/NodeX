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
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card font-mono"
          >
            <option value="ALL">All Statuses</option>
            <option value="SUCCESS">Delivered</option>
            <option value="FAILED">Failed</option>
          </select>
          <button
            onClick={loadData}
            aria-label="Refresh alerts"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card text-slate-500 hover:text-cyan-500"
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
              <td className="py-3 px-4 flex items-center gap-2 uppercase font-mono">
                <Send className="w-3.5 h-3.5 text-cyan-500" />
                {al.alert_type || 'telegram'}
              </td>
              <td className="py-3 px-4"><Badge variant={al.event_type}>{al.event_type || 'SECURITY_EVENT'}</Badge></td>
              <td className="py-3 px-4 font-mono">
                {al.success ? (
                  <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" /> Delivered
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                    <AlertCircle className="w-4 h-4" /> Failed
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
