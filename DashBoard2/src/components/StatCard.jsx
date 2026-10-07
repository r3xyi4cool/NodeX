// Large visual statistic metric card with icon and animated counter
import React from 'react';
import { Card } from './Card';
import { AnimatedNumber } from './AnimatedNumber';

export function StatCard({ title, value, subtitle, icon: Icon, color = 'cyan', change }) {
  const colorMap = {
    cyan: 'text-[#006eff] bg-[#006eff]/15 border-[#006eff]/35 shadow-[0_0_16px_rgba(0,110,255,0.25)]',
    green: 'text-[#34d399] bg-[#34d399]/15 border-[#34d399]/35 shadow-[0_0_16px_rgba(52,211,153,0.2)]',
    amber: 'text-[#fbbf24] bg-[#fbbf24]/15 border-[#fbbf24]/35 shadow-[0_0_16px_rgba(251,191,36,0.2)]',
    orange: 'text-[#fb923c] bg-[#fb923c]/15 border-[#fb923c]/35 shadow-[0_0_16px_rgba(251,146,60,0.2)]',
    red: 'text-[#f87171] bg-[#f87171]/15 border-[#f87171]/35 shadow-[0_0_16px_rgba(248,113,113,0.2)]',
    slate: 'text-[#c9d1de] bg-white/5 border-white/15',
  };

  const badgeClass = colorMap[color] || colorMap.cyan;

  return (
    <Card hover className="relative overflow-hidden group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-mono font-semibold uppercase tracking-wider text-[#c9d1de]">
            {title}
          </p>
          <div className="mt-2 text-3xl font-bold font-mono tracking-tight text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.2)]">
            <AnimatedNumber value={value} />
          </div>
          {subtitle && (
            <p className="mt-1 text-xs text-[#7c8ba1]">{subtitle}</p>
          )}
          {change && (
            <span className="inline-block mt-2 text-xs font-mono font-medium text-[#34d399]">
              {change}
            </span>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-2xl border ${badgeClass} transition-all duration-300 group-hover:scale-110`}>
            <Icon className="w-6 h-6" aria-hidden="true" />
          </div>
        )}
      </div>
    </Card>
  );
}
