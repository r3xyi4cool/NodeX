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
      <div className="w-14 h-14 rounded-2xl bg-[#f87171]/12 border border-[#f87171]/30 flex items-center justify-center text-[#f87171] mb-3 shadow-[0_0_16px_rgba(248,113,113,0.2)]">
        <AlertCircle className="w-7 h-7" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-bold text-white mb-1">
        {title}
      </h3>
      <p className="text-xs text-[#c9d1de] max-w-sm mb-4">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="btn-cyber-pill border-[#006eff] bg-[#006eff]/20 hover:bg-[#006eff]/30 shadow-[0_0_20px_rgba(0,110,255,0.35)]"
        >
          <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
          Retry Request
        </button>
      )}
    </div>
  );
}
