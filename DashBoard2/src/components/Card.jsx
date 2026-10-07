// Reusable glassmorphic container card matching Dashboard 1 visual design
import React from 'react';

export function Card({ title, subtitle, action, children, className = '', hover = true }) {
  return (
    <div
      className={`rounded-xl border transition-all duration-200 overflow-hidden ${
        hover ? 'hover:border-cyan-500/40 dark:hover:border-nodex-border-glow hover:shadow-lg' : ''
      } bg-white border-slate-200 shadow-sm dark:bg-nodex-card dark:border-nodex-border dark:shadow-card ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 dark:border-nodex-border/60">
          <div>
            {title && (
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-nodex-secondary">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 dark:text-nodex-dim mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
