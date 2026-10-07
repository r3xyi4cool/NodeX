// Clean responsive data table container with styled column headers
import React from 'react';

export function Table({ columns = [], children, className = '' }) {
  return (
    <div className={`overflow-x-auto rounded-2xl border border-white/10 bg-[#000c24]/65 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,3,8,0.5)] ${className}`}>
      <table className="w-full text-left text-xs">
        <thead className="bg-white/[0.03] border-b border-white/10 text-[#c9d1de] uppercase tracking-wider font-semibold font-mono">
          <tr>
            {columns.map((col, idx) => (
              <th
                key={idx}
                className={`py-4 px-4 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.06] font-mono">
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
          ? 'cursor-pointer hover:bg-[#006eff]/10 focus:outline-none focus:bg-[#006eff]/15'
          : 'hover:bg-white/[0.03]'
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
