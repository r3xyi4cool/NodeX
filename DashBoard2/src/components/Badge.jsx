// Status badge component with token-mapped WCAG AA compliant colors
import React from 'react';

const VARIANTS = {
  // Security states & event types
  ARMED: 'bg-[#34d399]/12 text-[#34d399] border-[#34d399]/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',
  RECOVERED: 'bg-[#34d399]/12 text-[#34d399] border-[#34d399]/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',
  TOKEN_RECOVERED: 'bg-[#34d399]/12 text-[#34d399] border-[#34d399]/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',
  BLE_RECOVERED_FAST: 'bg-[#34d399]/12 text-[#34d399] border-[#34d399]/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',
  ONLINE: 'bg-[#34d399]/12 text-[#34d399] border-[#34d399]/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',

  BLE_LOST: 'bg-[#fbbf24]/12 text-[#fbbf24] border-[#fbbf24]/30 shadow-[0_0_10px_rgba(251,191,36,0.15)]',
  GRACE_PERIOD: 'bg-[#fbbf24]/12 text-[#fbbf24] border-[#fbbf24]/30 shadow-[0_0_10px_rgba(251,191,36,0.15)]',
  GRACE_STARTED: 'bg-[#fbbf24]/12 text-[#fbbf24] border-[#fbbf24]/30 shadow-[0_0_10px_rgba(251,191,36,0.15)]',

  SECURITY_EVENT: 'bg-[#f87171]/12 text-[#f87171] border-[#f87171]/30 shadow-[0_0_10px_rgba(248,113,113,0.15)]',
  LOCKED: 'bg-[#ef4444]/12 text-[#ef4444] border-[#ef4444]/30 shadow-[0_0_10px_rgba(239,68,68,0.15)]',
  OFFLINE: 'bg-[#f87171]/12 text-[#f87171] border-[#f87171]/30 shadow-[0_0_10px_rgba(248,113,113,0.15)]',

  MANUAL_TEST: 'bg-[#006eff]/15 text-[#006eff] border-[#006eff]/35 shadow-[0_0_12px_rgba(0,110,255,0.2)]',
  ALERT_TELEGRAM: 'bg-[#006eff]/15 text-[#006eff] border-[#006eff]/35 shadow-[0_0_12px_rgba(0,110,255,0.2)]',
  HEARTBEAT: 'bg-[#818cf8]/15 text-[#818cf8] border-[#818cf8]/30',

  DISARMED: 'bg-white/5 text-[#c9d1de] border-white/15',
  DEFAULT: 'bg-white/5 text-[#c9d1de] border-white/15',
};

export function Badge({ children, variant, size = 'sm', className = '' }) {
  const normKey = String(variant || children || '').trim().toUpperCase();
  const colorStyle = VARIANTS[normKey] || VARIANTS.DEFAULT;
  const sizeStyle = size === 'xs' ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-full border backdrop-blur-md ${colorStyle} ${sizeStyle} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-90 shadow-[0_0_6px_currentColor]" aria-hidden="true" />
      {children}
    </span>
  );
}
