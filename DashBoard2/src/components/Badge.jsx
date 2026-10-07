// Status badge component with token-mapped WCAG AA compliant colors
import React from 'react';

const VARIANTS = {
  // Security states & event types
  ARMED: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
  RECOVERED: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
  TOKEN_RECOVERED: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
  BLE_RECOVERED_FAST: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
  ONLINE: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',

  BLE_LOST: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30',
  GRACE_PERIOD: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30',
  GRACE_STARTED: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30',

  SECURITY_EVENT: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30',
  LOCKED: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30',
  OFFLINE: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30',

  MANUAL_TEST: 'bg-sky-500/15 text-sky-700 dark:text-sky-400 border-sky-500/30',
  ALERT_TELEGRAM: 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/30',
  HEARTBEAT: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-400 border-indigo-500/30',

  DISARMED: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30',
  DEFAULT: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30',
};

export function Badge({ children, variant, size = 'sm', className = '' }) {
  const normKey = String(variant || children || '').trim().toUpperCase();
  const colorStyle = VARIANTS[normKey] || VARIANTS.DEFAULT;
  const sizeStyle = size === 'xs' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-full border ${colorStyle} ${sizeStyle} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" aria-hidden="true" />
      {children}
    </span>
  );
}
