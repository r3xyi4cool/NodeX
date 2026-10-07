// Statistics and analytics dashboard with SVG visualisations of event distributions and recovery metrics
import React, { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { StatCard } from '../components/StatCard';
import { BarChart } from '../components/BarChart';
import { CardSkeleton } from '../components/Skeleton';
import { ErrorState } from '../components/ErrorState';
import { getEventStats, getAlerts } from '../lib/supabase';
import { Activity, ShieldCheck, Bell, BarChart2 } from 'lucide-react';

export function Stats() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dailyData, setDailyData] = useState([]);
  const [typeDistribution, setTypeDistribution] = useState([]);
  const [recoveryRate, setRecoveryRate] = useState(100);
  const [alertsCount, setAlertsCount] = useState(0);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [events, alerts] = await Promise.all([getEventStats(), getAlerts({ limit: 100 })]);

      // Group by day
      const dayMap = {};
      const typeMap = {};
      let disconnects = 0;
      let recoveries = 0;

      events.forEach((ev) => {
        const d = new Date(ev.created_at).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' });
        dayMap[d] = (dayMap[d] || 0) + 1;
        typeMap[ev.event_type] = (typeMap[ev.event_type] || 0) + 1;

        if (ev.event_type === 'BLE_LOST') disconnects++;
        if (ev.event_type === 'TOKEN_RECOVERED' || ev.event_type === 'BLE_RECOVERED_FAST') recoveries++;
      });

      const dayArr = Object.entries(dayMap).slice(-7).map(([label, value]) => ({ label, value }));
      setDailyData(dayArr.length ? dayArr : [{ label: 'Today', value: events.length }]);

      const totalEv = events.length || 1;
      const typeArr = Object.entries(typeMap).map(([type, count]) => ({
        type,
        count,
        percent: Math.round((count / totalEv) * 100),
      }));
      setTypeDistribution(typeArr);

      const rate = disconnects > 0 ? Math.min(Math.round((recoveries / disconnects) * 100), 100) : 100;
      setRecoveryRate(rate);
      setAlertsCount(alerts.length);
    } catch (err) {
      setError(err.message || 'Failed to compute security analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <div className="space-y-4"><CardSkeleton /><CardSkeleton /></div>;
  if (error) return <ErrorState message={error} onRetry={loadData} />;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard title="Proximity Recovery Rate" value={`${recoveryRate}%`} icon={ShieldCheck} color="green" subtitle="Recoveries during grace period" />
        <StatCard title="Alert Channels Dispatched" value={alertsCount} icon={Bell} color="cyan" subtitle="Telegram security dispatches" />
        <StatCard title="Distinct Event Types" value={typeDistribution.length} icon={BarChart2} color="slate" subtitle="Logged in system audit history" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Daily Event Volume" subtitle="Aggregated security events by date">
          <BarChart data={dailyData} height={200} />
        </Card>

        <Card title="Event Type Distribution" subtitle="Proportional breakdown across all event categories">
          <div className="space-y-4 font-mono text-xs">
            {typeDistribution.map((item) => (
              <div key={item.type}>
                <div className="flex justify-between text-slate-700 dark:text-slate-200 mb-1.5 font-medium">
                  <span className="text-slate-300">{item.type}</span>
                  <span className="text-slate-400 font-semibold">{item.count} <span className="text-[#006eff]">({item.percent}%)</span></span>
                </div>
                <div className="w-full h-2.5 rounded-full bg-slate-100 dark:bg-white/5 overflow-hidden border border-slate-200/50 dark:border-white/10 p-[1px]">
                  <div
                    className="h-full bg-gradient-to-r from-[#006eff] to-[#00d2ff] rounded-full shadow-[0_0_8px_rgba(0,110,255,0.4)] transition-all duration-500"
                    style={{ width: `${item.percent}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
