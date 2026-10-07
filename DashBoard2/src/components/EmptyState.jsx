// Descriptive placeholder display when datasets or queries return zero items
import React from 'react';
import { Inbox } from 'lucide-react';

export function EmptyState({
  title = 'No Data Found',
  description = 'No records match your current filter criteria.',
  icon: Icon = Inbox,
  action,
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-nodex-card2 border border-slate-200 dark:border-nodex-border flex items-center justify-center text-slate-400 dark:text-nodex-secondary mb-3">
        <Icon className="w-6 h-6" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800 dark:text-nodex-primary mb-1">
        {title}
      </h3>
      <p className="text-xs text-slate-500 dark:text-nodex-dim max-w-sm mb-4">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
