// Hand-built SVG and CSS responsive bar chart without external charting libraries
import React, { useState } from 'react';

export function BarChart({ data = [], height = 180, className = '' }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  if (!data || data.length === 0) {
    return <div className="h-40 flex items-center justify-center text-xs text-slate-400">No chart data</div>;
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1);
  const barWidth = 24;
  const gap = 16;
  const chartWidth = Math.max(data.length * (barWidth + gap) + 20, 280);

  return (
    <div className={`w-full overflow-x-auto ${className}`}>
      <svg
        viewBox={`0 0 ${chartWidth} ${height + 40}`}
        className="w-full h-auto min-w-[280px]"
        preserveAspectRatio="xMidYMid meet"
      >
        <line
          x1="10"
          y1={height}
          x2={chartWidth - 10}
          y2={height}
          stroke="currentColor"
          className="text-slate-200 dark:text-slate-800"
          strokeWidth="1"
        />

        {data.map((item, idx) => {
          const x = 20 + idx * (barWidth + gap);
          const barHeight = Math.max((item.value / maxValue) * (height - 20), 4);
          const y = height - barHeight;
          const isHovered = hoveredIdx === idx;

          return (
            <g
              key={idx}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
              className="cursor-pointer transition-opacity"
            >
              {/* Highlight background */}
              {isHovered && (
                <rect
                  x={x - 4}
                  y="10"
                  width={barWidth + 8}
                  height={height + 25}
                  rx="6"
                  className="fill-cyan-500/10 dark:fill-nodex-cyan/10"
                />
              )}

              {/* Bar */}
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                rx="4"
                className={`transition-all duration-300 ${
                  isHovered
                    ? 'fill-cyan-500 dark:fill-nodex-cyan'
                    : 'fill-cyan-600/70 dark:fill-cyan-400/60'
                }`}
              />

              {/* Hover Value */}
              {isHovered && (
                <text
                  x={x + barWidth / 2}
                  y={Math.max(y - 6, 12)}
                  textAnchor="middle"
                  className="text-[10px] font-mono font-bold fill-slate-800 dark:fill-white"
                >
                  {item.value}
                </text>
              )}

              {/* Label */}
              <text
                x={x + barWidth / 2}
                y={height + 16}
                textAnchor="middle"
                className="text-[9px] font-mono fill-slate-500 dark:fill-slate-400"
              >
                {item.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
