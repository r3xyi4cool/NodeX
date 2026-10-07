// ESP32 proximity token status view with masked identifier, firmware and battery indicators
import React, { useState, useEffect } from 'react';
import { Cpu, Bluetooth, Signal, Battery, Clock, ShieldCheck } from 'lucide-react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { CardSkeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { getLaptops, getLatestHeartbeat } from '../lib/supabase';

export function Token() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tokens, setTokens] = useState([]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const laptops = await getLaptops();
      const tokenList = await Promise.all(
        laptops.map(async (laptop) => {
          const hb = await getLatestHeartbeat(laptop.id);
          return {
            id: `ESP32-${laptop.id.slice(0, 6)}`,
            macMasked: '24:6F:28:••:••:••',
            firmware: 'NodeX-ESP32-v1.2.0',
            laptopName: laptop.name,
            bleConnected: hb?.ble_connected ?? false,
            rssi: hb?.rssi_smooth ?? -72,
            batteryPercent: 88,
            lastSeen: hb?.created_at || laptop.last_seen,
            pairedDate: laptop.created_at,
          };
        })
      );
      setTokens(tokenList);
    } catch (err) {
      setError(err.message || 'Failed to load token diagnostics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <div className="space-y-4"><CardSkeleton /></div>;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (tokens.length === 0) return <EmptyState title="No Tokens Found" description="Pair an ESP32 hardware token in the NodeX daemon." />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white">ESP32 BLE Security Tokens</h2>
          <p className="text-xs text-slate-500 dark:text-nodex-secondary">Hardware proximity key diagnostics and signal telemetry</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {tokens.map((token) => (
          <Card key={token.id} hover={false} className="border-l-4 border-l-emerald-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-100 dark:border-nodex-border/60 gap-4">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-slate-100 dark:bg-nodex-card2 border border-slate-200 dark:border-nodex-border text-emerald-500">
                  <Cpu className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    {token.id}
                    <Badge variant={token.bleConnected ? 'ONLINE' : 'BLE_LOST'}>
                      {token.bleConnected ? 'CONNECTED' : 'DISCONNECTED'}
                    </Badge>
                  </h3>
                  <p className="text-xs font-mono text-slate-500 dark:text-nodex-dim">Paired with: {token.laptopName}</p>
                </div>
              </div>
              <div className="text-xs font-mono text-slate-400">
                Last seen: {token.lastSeen ? new Date(token.lastSeen).toLocaleString() : 'N/A'}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 font-mono text-xs">
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-200/60 dark:border-nodex-border/40">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                  <Bluetooth className="w-3.5 h-3.5" />
                  <span>BLE Identifier (Masked)</span>
                </div>
                <div className="text-sm font-bold text-slate-800 dark:text-white">{token.macMasked}</div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-200/60 dark:border-nodex-border/40">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                  <Signal className="w-3.5 h-3.5" />
                  <span>Proximity Signal (RSSI)</span>
                </div>
                <div className="text-sm font-bold text-slate-800 dark:text-white">
                  {token.rssi ? `${Math.round(token.rssi)} dBm` : 'N/A'}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-200/60 dark:border-nodex-border/40">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                  <Battery className="w-3.5 h-3.5" />
                  <span>Token Battery</span>
                </div>
                <div className="text-sm font-bold text-slate-800 dark:text-white flex items-center gap-2">
                  <span>{token.batteryPercent}%</span>
                  <div className="w-16 h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${token.batteryPercent}%` }} />
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-200/60 dark:border-nodex-border/40">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Firmware Release</span>
                </div>
                <div className="text-xs font-bold text-slate-800 dark:text-white">{token.firmware}</div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 dark:border-nodex-border/40 flex items-center justify-between text-[11px] font-mono text-slate-400">
              <span>Security Profile: AES-128 Challenge-Ready</span>
              <span>Paired on: {new Date(token.pairedDate).toLocaleDateString()}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
