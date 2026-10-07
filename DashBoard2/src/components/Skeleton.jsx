// Animated pulse placeholder shimmer for loading states
import React from 'react';

export function Skeleton({ className = '', variant = 'rect' }) {
  const base = 'animate-pulse bg-slate-200 dark:bg-slate-800/80';
  const shape = variant === 'circle' ? 'rounded-full' : 'rounded-lg';
  return <div className={`${base} ${shape} ${className}`} aria-hidden="true" />;
}

export function TableSkeleton({ rows = 5, cols = 5 }) {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-8 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 items-center">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-6 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="p-6 rounded-xl border border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card space-y-4">
      <div className="flex justify-between items-center">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-8" variant="circle" />
      </div>
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-3 w-36" />
    </div>
  );
}
