import React, { useState } from 'react';
import { Menu, RefreshCw, AlertTriangle, CheckCircle, WifiOff, X, Database, ShieldAlert } from 'lucide-react';
import { useData } from '../context/DataContext';

export function TopBar({ onOpenSidebar }) {
  const {
    lastRefreshed,
    isRefreshing,
    refreshError,
    refreshData,
    connectivity,
    runConnectivityCheck,
    clearRefreshError,
  } = useData();

  const [connModalOpen, setConnModalOpen] = useState(false);
  const [testingConn, setTestingConn] = useState(false);

  const handleTestConnection = async () => {
    setTestingConn(true);
    await runConnectivityCheck();
    setTestingConn(false);
  };

  const isConnected = connectivity.status === 'CONNECTED';
  const isChecking = connectivity.status === 'CHECKING';
  const isFailed = connectivity.status === 'FAILED';

  return (
    <>
      <header className="sticky top-0 z-30 px-4 sm:px-6 lg:px-8 py-3.5 border-b border-slate-200 dark:border-nodex-border bg-white/80 dark:bg-nodex-card/80 backdrop-blur-md flex items-center justify-between gap-4">
        {/* Left: Mobile hamburger & title */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenSidebar}
            aria-label="Open sidebar menu"
            className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.04]"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-slate-900 dark:text-white">
              Node<span className="text-cyan-500">X</span> Cloud
            </span>
            <span className="hidden sm:inline-block text-[11px] font-mono text-slate-400 dark:text-nodex-dim">
              Synchronized Anti-Theft Monitor
            </span>
          </div>
        </div>

        {/* Right: Connectivity Status + Refresh Data Button */}
        <div className="flex items-center gap-3">
          {/* Supabase Connectivity Indicator */}
          <button
            onClick={() => setConnModalOpen(true)}
            title="Click to view Supabase connection status & diagnostics"
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono transition-all border ${
              isConnected
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/25 hover:bg-emerald-500/20'
                : isChecking
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/25'
                : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30 hover:bg-rose-500/20 animate-pulse'
            }`}
          >
            {isConnected && (
              <>
                <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500" />
                <span className="hidden md:inline">Supabase</span>
                <span>Connected</span>
              </>
            )}
            {isChecking && (
              <>
                <RefreshCw className="w-3 h-3 animate-spin text-amber-500" />
                <span className="hidden md:inline">Checking</span>
                <span>Connection…</span>
              </>
            )}
            {isFailed && (
              <>
                <div className="w-2 h-2 rounded-full bg-rose-500" />
                <span className="hidden md:inline">Supabase</span>
                <span>Connection Failed</span>
              </>
            )}
          </button>

          {/* Refresh Data Button */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={refreshData}
              disabled={isRefreshing}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold tracking-wide transition-all border shadow-sm ${
                isRefreshing
                  ? 'bg-slate-100 dark:bg-nodex-card2 text-slate-400 dark:text-nodex-dim border-slate-200 dark:border-nodex-border cursor-wait'
                  : 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border-cyan-500/30 hover:border-cyan-500/50 hover:shadow-cyan-500/10'
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
              <span>{isRefreshing ? 'Refreshing…' : 'Refresh Data'}</span>
            </button>

            {/* Last Refreshed Timestamp */}
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-[10px] text-slate-400 dark:text-nodex-dim uppercase font-mono tracking-wider">
                Last Refreshed
              </span>
              <span className="text-xs font-mono font-medium text-slate-700 dark:text-nodex-secondary">
                {lastRefreshed ? lastRefreshed.toLocaleTimeString() : '—'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Dismissible Warning Banner on Refresh Error */}
      {refreshError && (
        <div className="mx-4 sm:mx-6 lg:mx-8 mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500" />
            <span>
              Refresh warning: {refreshError}. Preserving previously loaded telemetry data.
            </span>
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            <button
              onClick={refreshData}
              className="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-600 dark:text-amber-300 font-semibold"
            >
              Retry
            </button>
            <button
              onClick={clearRefreshError}
              aria-label="Dismiss error"
              className="p-1 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Connectivity Diagnostics Modal */}
      {connModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-nodex-card border border-slate-200 dark:border-nodex-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-nodex-border/60">
              <div className="flex items-center gap-2.5">
                <Database className="w-5 h-5 text-cyan-500" />
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  Supabase Connectivity Diagnostics
                </h3>
              </div>
              <button
                onClick={() => setConnModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-white rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-nodex-card2 border border-slate-200 dark:border-nodex-border text-xs space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400 dark:text-nodex-dim">Status:</span>
                  <span
                    className={`font-bold ${
                      isConnected
                        ? 'text-emerald-500'
                        : isChecking
                        ? 'text-amber-500'
                        : 'text-rose-500'
                    }`}
                  >
                    {connectivity.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400 dark:text-nodex-dim">Category:</span>
                  <span className="text-slate-700 dark:text-nodex-primary">
                    {connectivity.category || 'General'}
                  </span>
                </div>
              </div>

              <div className="text-xs text-slate-600 dark:text-nodex-secondary leading-relaxed p-3 rounded-xl bg-slate-100/60 dark:bg-white/[0.02] border border-slate-200/60 dark:border-nodex-border/40">
                {connectivity.message || 'No details available.'}
              </div>

              {isFailed && (
                <div className="text-[11px] text-slate-400 dark:text-nodex-dim italic">
                  Note: Sensitive secrets and authentication tokens are masked to maintain security.
                </div>
              )}
            </div>

            <div className="flex gap-2.5 pt-2">
              <button
                onClick={() => setConnModalOpen(false)}
                className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-nodex-card2 text-slate-600 dark:text-nodex-secondary hover:text-slate-900 dark:hover:text-white transition-colors"
              >
                Close
              </button>
              <button
                onClick={handleTestConnection}
                disabled={testingConn}
                className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30 flex items-center justify-center gap-1.5 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${testingConn ? 'animate-spin' : ''}`} />
                <span>{testingConn ? 'Testing…' : 'Retest Connectivity'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

