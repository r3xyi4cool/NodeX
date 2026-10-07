// Graceful error display with descriptive message and interactive retry button
import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export function ErrorState({
  title = 'Failed to load data',
  message = 'An unexpected network error occurred while contacting Supabase.',
  onRetry,
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-500 dark:text-nodex-red mb-3">
        <AlertCircle className="w-6 h-6" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800 dark:text-nodex-primary mb-1">
        {title}
      </h3>
      <p className="text-xs text-slate-500 dark:text-nodex-dim max-w-sm mb-4">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white shadow transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
        >
          <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
          Retry Request
        </button>
      )}
    </div>
  );
}
