// Theme switcher supporting dark, light and system mode options
import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

export function ThemeToggle({ className = '' }) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className={`inline-flex items-center p-1 rounded-lg border border-slate-200 dark:border-nodex-border bg-slate-100 dark:bg-nodex-card2 ${className}`}
      role="group"
      aria-label="Theme switcher"
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        aria-label="Light mode"
        aria-pressed={theme === 'light'}
        className={`p-1.5 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500 ${
          theme === 'light'
            ? 'bg-white text-amber-500 shadow-sm'
            : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
        }`}
      >
        <Sun className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('dark')}
        aria-label="Dark mode"
        aria-pressed={theme === 'dark'}
        className={`p-1.5 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500 ${
          theme === 'dark'
            ? 'bg-nodex-card text-nodex-cyan shadow-sm'
            : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
        }`}
      >
        <Moon className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('system')}
        aria-label="System mode"
        aria-pressed={theme === 'system'}
        className={`p-1.5 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-cyan-500 ${
          theme === 'system'
            ? 'bg-white dark:bg-nodex-card text-cyan-600 dark:text-nodex-cyan shadow-sm'
            : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
        }`}
      >
        <Monitor className="w-4 h-4" />
      </button>
    </div>
  );
}
