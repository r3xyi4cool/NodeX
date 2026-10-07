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
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 flex flex-col bg-[#000511]/92 backdrop-blur-2xl border-r border-white/10 transition-transform duration-300 lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-[#006eff]/12 text-[#006eff] border border-[#006eff]/30 shadow-[0_0_16px_rgba(0,110,255,0.25)]">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <span className="font-medium italic text-lg tracking-tight text-white font-sans">
                Node<b className="text-[#006eff] not-italic font-bold">X</b>
              </span>
              <span className="ml-2 text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-white/5 text-[#c9d1de] border border-white/15">
                Cloud
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="lg:hidden p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-2" aria-label="Main Navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 rounded-full text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-[#006eff]/15 text-white font-semibold border border-[#006eff]/40 shadow-[0_0_20px_rgba(0,110,255,0.3)]'
                      : 'text-[#c9d1de] hover:bg-white/[0.04] hover:text-white border border-transparent hover:border-white/10'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-white/10 space-y-3 bg-[#000308]/40">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#c9d1de] font-mono">Theme</span>
            <ThemeToggle />
          </div>

          <div className="pt-2 border-t border-white/10 flex items-center justify-between">
            <div className="truncate max-w-[130px]">
              <p className="text-[10px] font-mono text-[#7c8ba1] truncate">
                {userEmail || 'Authenticated'}
              </p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out of Supabase"
              aria-label="Sign out"
              className="p-1.5 rounded-full border border-white/15 text-[#c9d1de] hover:text-[#f87171] hover:border-[#f87171]/40 hover:bg-[#f87171]/10 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
