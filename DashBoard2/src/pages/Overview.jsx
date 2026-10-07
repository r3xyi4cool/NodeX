// Overview summary dashboard displaying key security stats, telemetry status, chart and latest events
import React, { useState, useEffect } from 'react';
import { Shield, AlertTriangle, RefreshCw, Bell, Laptop, Terminal, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatCard } from '../components/StatCard';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { BarChart } from '../components/BarChart';
import { Skeleton, CardSkeleton } from '../components/Skeleton';
import { ErrorState } from '../components/ErrorState';
import { getLaptops, getRecentEvents, getEventStats, getCaptures, getAlerts, getSignedPhotoUrl } from '../lib/supabase';

export function Overview({ onOpenLightbox }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [laptops, setLaptops] = useState([]);
  const [recentEvents, setRecentEvents] = useState([]);
  const [captures, setCaptures] = useState([]);
  const [stats, setStats] = useState({ total: 0, disconnects: 0, recoveries: 0, alerts: 0, tests: 0 });
  const [chartData, setChartData] = useState([]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [laptopsData, eventsData, allStats, capturesData, alertsData] = await Promise.all([
        getLaptops(),
        getRecentEvents(5),
        getEventStats(),
        getCaptures({ limit: 4 }),
        getAlerts({ limit: 50 }),
      ]);

      setLaptops(laptopsData);
      setRecentEvents(eventsData);

      // Photos with signed URLs
      const signedCaptures = await Promise.all(
        capturesData.map(async (c) => ({
          ...c,
          url: await getSignedPhotoUrl(c.storage_path),
        }))
      );
      setCaptures(signedCaptures);

      // Compute statistics
      let disconnects = 0;
      let recoveries = 0;
      let tests = 0;
      const dayMap = {};

      allStats.forEach((ev) => {
        if (ev.event_type === 'BLE_LOST') disconnects++;
        if (ev.event_type === 'TOKEN_RECOVERED' || ev.event_type === 'BLE_RECOVERED_FAST') recoveries++;
        if (ev.event_type === 'MANUAL_TEST') tests++;
        const dateKey = new Date(ev.created_at).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' });
        dayMap[dateKey] = (dayMap[dateKey] || 0) + 1;
      });

      setStats({
        total: allStats.length,
        disconnects,
        recoveries,
        alerts: alertsData.length,
        tests,
      });

      const chartArr = Object.entries(dayMap).slice(-7).map(([label, value]) => ({ label, value }));
      setChartData(chartArr.length ? chartArr : [{ label: 'Today', value: allStats.length }]);
    } catch (err) {
      setError(err.message || 'Error loading dashboard telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  if (error) return <ErrorState message={error} onRetry={loadData} />;

  const primaryLaptop = laptops[0];
  const isOnline = primaryLaptop?.last_seen && (Date.now() - new Date(primaryLaptop.last_seen).getTime()) < 90000;

  return (
    <div className="space-y-6">
      {/* Laptop Status Header Banner */}
      <Card hover={false} className="border-l-4 border-l-[#006eff] bg-gradient-to-r from-[#001233]/70 via-[#000d26]/80 to-[#000511]/90">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className={`p-3 rounded-2xl border ${isOnline ? 'border-[#34d399]/40 bg-[#34d399]/15 text-[#34d399] shadow-[0_0_16px_rgba(52,211,153,0.25)]' : 'border-[#f87171]/40 bg-[#f87171]/15 text-[#f87171] shadow-[0_0_16px_rgba(248,113,113,0.25)]'}`}>
              <Laptop className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-sm font-bold text-white font-sans">
                  {primaryLaptop?.name || 'No Registered Laptop'}
                </h2>
                <Badge variant={isOnline ? 'ONLINE' : 'OFFLINE'}>
                  {isOnline ? 'ONLINE' : 'OFFLINE'}
                </Badge>
              </div>
              <p className="text-xs text-[#c9d1de] mt-0.5 font-sans">
                {isOnline
                  ? `Active & Monitoring • Mode: ${primaryLaptop?.security_mode || 'DISARMED'}`
                  : primaryLaptop?.last_seen
                  ? `Offline since ${new Date(primaryLaptop.last_seen).toLocaleTimeString()}`
                  : 'No heartbeat recorded yet'}
              </p>
            </div>
          </div>
          <button
            onClick={loadData}
            aria-label="Refresh telemetry data"
            className="btn-cyber-pill border-white/20 bg-white/[0.04] hover:bg-[#006eff]/20 hover:border-[#006eff] hover:shadow-[0_0_20px_rgba(0,110,255,0.4)] text-xs text-[#c9d1de] hover:text-white"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </Card>

      {/* 5 Big Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard title="Total Events" value={stats.total} icon={Shield} color="cyan" />
        <StatCard title="BLE Disconnects" value={stats.disconnects} icon={AlertTriangle} color="amber" />
        <StatCard title="Recoveries" value={stats.recoveries} icon={RefreshCw} color="green" />
        <StatCard title="Alerts Fired" value={stats.alerts} icon={Bell} color="red" />
        <StatCard title="Manual Tests" value={stats.tests} icon={Terminal} color="slate" />
      </div>

      {/* Bar Chart & Recent Events */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <Card title="Security Events History" subtitle="Events logged per calendar day">
            <BarChart data={chartData} height={160} />
          </Card>
        </div>
        <div className="lg:col-span-5">
          <Card
            title="Latest Security Events"
            subtitle="Most recent audit logs"
            action={<Link to="/events" className="text-xs font-mono text-[#006eff] flex items-center gap-1 hover:underline">View All <ExternalLink className="w-3 h-3" /></Link>}
          >
            <div className="space-y-3 font-mono">
              {recentEvents.map((ev) => (
                <div key={ev.id} className="flex items-center justify-between text-xs py-2 border-b border-white/[0.06] last:border-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={ev.event_type}>{ev.event_type}</Badge>
                    <span className="text-[#c9d1de] text-[11px] truncate max-w-[120px]">{ev.laptops?.name || 'Device'}</span>
                  </div>
                  <span className="text-[11px] text-[#7c8ba1]">{new Date(ev.created_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Latest Photos Grid */}
      <Card
        title="Recent Intruder Captures"
        subtitle="Last 4 webcam surveillance frames (20-photo ring buffer)"
        action={<Link to="/captures" className="text-xs font-mono text-[#006eff] flex items-center gap-1 hover:underline">Gallery <ExternalLink className="w-3 h-3" /></Link>}
      >
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {captures.map((c, idx) => (
            <div
              key={c.id || idx}
              onClick={() => onOpenLightbox && onOpenLightbox(captures, idx)}
              className="group relative rounded-2xl overflow-hidden border border-white/10 bg-black aspect-video cursor-pointer hover:border-[#006eff]/50 hover:shadow-[0_0_20px_rgba(0,110,255,0.25)] transition-all"
            >
              <img src={c.url} alt={`Slot ${c.slot}`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-95 p-2.5 flex flex-col justify-end text-[10px] font-mono text-white">
                <span className="font-semibold text-white">Slot {c.slot} • {c.security_mode}</span>
                <span className="text-[#c9d1de]">{new Date(c.captured_at).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
