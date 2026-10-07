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
      <div className="w-14 h-14 rounded-2xl bg-[#006eff]/12 border border-[#006eff]/30 flex items-center justify-center text-[#006eff] mb-3 shadow-[0_0_16px_rgba(0,110,255,0.25)]">
        <Icon className="w-7 h-7" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-bold text-white mb-1">
        {title}
      </h3>
      <p className="text-xs text-[#c9d1de] max-w-sm mb-4">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
