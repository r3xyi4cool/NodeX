// Large visual statistic metric card with icon and animated counter
import React from 'react';
import { Card } from './Card';
import { AnimatedNumber } from './AnimatedNumber';

export function StatCard({ title, value, subtitle, icon: Icon, color = 'cyan', change }) {
  const colorMap = {
    cyan: 'text-cyan-500 dark:text-nodex-cyan bg-cyan-500/10 border-cyan-500/20',
    green: 'text-emerald-500 dark:text-nodex-green bg-emerald-500/10 border-emerald-500/20',
    amber: 'text-amber-500 dark:text-nodex-amber bg-amber-500/10 border-amber-500/20',
    orange: 'text-orange-500 dark:text-nodex-orange bg-orange-500/10 border-orange-500/20',
    red: 'text-rose-500 dark:text-nodex-red bg-rose-500/10 border-rose-500/20',
    slate: 'text-slate-500 dark:text-slate-400 bg-slate-500/10 border-slate-500/20',
  };

  const badgeClass = colorMap[color] || colorMap.cyan;

  return (
    <Card hover className="relative overflow-hidden group">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-nodex-secondary">
            {title}
          </p>
          <div className="mt-2 text-3xl font-bold font-mono tracking-tight text-slate-900 dark:text-white">
            <AnimatedNumber value={value} />
          </div>
          {subtitle && (
            <p className="mt-1 text-xs text-slate-500 dark:text-nodex-secondary">{subtitle}</p>
          )}
          {change && (
            <span className="inline-block mt-2 text-xs font-mono font-medium text-emerald-500 dark:text-nodex-green">
              {change}
            </span>
          )}
        </div>
        {Icon && (
          <div className={`p-3 rounded-xl border ${badgeClass} transition-transform duration-200 group-hover:scale-110`}>
            <Icon className="w-6 h-6" aria-hidden="true" />
          </div>
        )}
      </div>
    </Card>
  );
}
