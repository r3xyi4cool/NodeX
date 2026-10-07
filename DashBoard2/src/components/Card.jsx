// Reusable glassmorphic container card matching Dashboard 1 visual design
import React from 'react';

export function Card({ title, subtitle, action, children, className = '', hover = true }) {
  return (
    <div
      className={`rounded-2xl border transition-all duration-300 overflow-hidden relative backdrop-blur-xl ${
        hover
          ? 'hover:border-[#006eff]/40 hover:shadow-[0_0_28px_rgba(0,110,255,0.2)]'
          : ''
      } bg-[#000c24]/65 border-white/10 shadow-[0_8px_32px_rgba(0,3,8,0.5)] ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.015]">
          <div>
            {title && (
              <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#c9d1de]">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-[#7c8ba1] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
