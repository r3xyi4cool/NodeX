// Animated pulse placeholder shimmer for loading states
import React from 'react';

export function Skeleton({ className = '', variant = 'rect' }) {
  const base = 'animate-pulse bg-white/[0.06] border border-white/[0.04]';
  const shape = variant === 'circle' ? 'rounded-full' : 'rounded-xl';
  return <div className={`${base} ${shape} ${className}`} aria-hidden="true" />;
}

export function TableSkeleton({ rows = 5, cols = 5 }) {
  return (
    <div className="space-y-3 p-4 rounded-2xl border border-white/10 bg-[#000c24]/65 backdrop-blur-xl">
      <Skeleton className="h-9 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 items-center">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-7 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="p-6 rounded-2xl border border-white/10 bg-[#000c24]/65 space-y-4 backdrop-blur-xl">
      <div className="flex justify-between items-center">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-8" variant="circle" />
      </div>
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-3 w-36" />
    </div>
  );
}
