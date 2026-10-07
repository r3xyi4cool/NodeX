// Clean responsive data table container with styled column headers
import React from 'react';

export function Table({ columns = [], children, className = '' }) {
  return (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card ${className}`}>
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 dark:bg-nodex-card2 border-b border-slate-200 dark:border-nodex-border/60 text-slate-500 dark:text-nodex-secondary uppercase tracking-wider font-semibold font-mono">
          <tr>
            {columns.map((col, idx) => (
              <th
                key={idx}
                className={`py-3.5 px-4 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-nodex-border/40 font-mono">
          {children}
        </tbody>
      </table>
    </div>
  );
}

export function TableRow({ children, onClick, className = '' }) {
  return (
    <tr
      onClick={onClick}
      className={`transition-colors duration-150 ${
        onClick
          ? 'cursor-pointer hover:bg-slate-50 dark:hover:bg-cyan-500/5 focus:outline-none focus:bg-slate-50 dark:focus:bg-cyan-500/10'
          : 'hover:bg-slate-50/60 dark:hover:bg-white/[0.02]'
      } ${className}`}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {children}
    </tr>
  );
}
