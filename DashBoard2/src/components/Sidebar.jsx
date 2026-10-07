// Collapsible left navigation sidebar with mobile drawer and session controls
import React from 'react';
import { NavLink } from 'react-router-dom';
import { Shield, LayoutDashboard, Laptop, Cpu, Activity, Camera, Bell, BarChart2, LogOut, X } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/laptop', label: 'Laptop Data', icon: Laptop },
  { to: '/token', label: 'ESP32 Token', icon: Cpu },
  { to: '/events', label: 'Security Events', icon: Activity },
  { to: '/captures', label: 'Captures Gallery', icon: Camera },
  { to: '/alerts', label: 'Alerts & Logs', icon: Bell },
  { to: '/stats', label: 'Statistics', icon: BarChart2 },
];

export function Sidebar({ isOpen, onClose, onLogout, userEmail }) {
  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/50 lg:hidden backdrop-blur-sm"
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 flex flex-col bg-white dark:bg-nodex-card border-r border-slate-200 dark:border-nodex-border transition-transform duration-300 lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-nodex-border/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-600 dark:text-nodex-cyan border border-cyan-500/20">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-base text-slate-900 dark:text-white">
                Node<span className="text-cyan-500 dark:text-nodex-cyan">X</span>
              </span>
              <span className="ml-1.5 text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-nodex-card2 text-slate-500 dark:text-nodex-secondary border border-slate-200 dark:border-nodex-border">
                Cloud
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="lg:hidden p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1.5" aria-label="Main Navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-600 dark:text-nodex-cyan font-semibold border border-cyan-500/20'
                      : 'text-slate-600 dark:text-nodex-secondary hover:bg-slate-100 dark:hover:bg-white/[0.03] hover:text-slate-900 dark:hover:text-white'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-100 dark:border-nodex-border/60 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 dark:text-nodex-dim font-mono">Theme</span>
            <ThemeToggle />
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-nodex-border/40 flex items-center justify-between">
            <div className="truncate max-w-[130px]">
              <p className="text-[10px] font-mono text-slate-400 dark:text-nodex-dim truncate">
                {userEmail || 'Authenticated'}
              </p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out of Supabase"
              aria-label="Sign out"
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-500 dark:hover:text-nodex-red hover:bg-rose-500/10 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
