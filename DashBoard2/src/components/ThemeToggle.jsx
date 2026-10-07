// Theme switcher supporting dark, light and system mode options
import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

export function ThemeToggle({ className = '' }) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className={`inline-flex items-center p-1 rounded-full border border-white/15 bg-white/[0.03] backdrop-blur-md ${className}`}
      role="group"
      aria-label="Theme switcher"
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        aria-label="Light mode"
        aria-pressed={theme === 'light'}
        className={`p-1.5 rounded-full transition-all focus:outline-none ${
          theme === 'light'
            ? 'bg-white/15 text-[#fbbf24] border border-white/25 shadow-sm'
            : 'text-[#7c8ba1] hover:text-white'
        }`}
      >
        <Sun className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('dark')}
        aria-label="Dark mode"
        aria-pressed={theme === 'dark'}
        className={`p-1.5 rounded-full transition-all focus:outline-none ${
          theme === 'dark'
            ? 'bg-[#006eff]/20 text-[#006eff] border border-[#006eff]/40 shadow-[0_0_12px_rgba(0,110,255,0.35)]'
            : 'text-[#7c8ba1] hover:text-white'
        }`}
      >
        <Moon className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setTheme('system')}
        aria-label="System mode"
        aria-pressed={theme === 'system'}
        className={`p-1.5 rounded-full transition-all focus:outline-none ${
          theme === 'system'
            ? 'bg-[#006eff]/20 text-white border border-[#006eff]/40 shadow-[0_0_12px_rgba(0,110,255,0.35)]'
            : 'text-[#7c8ba1] hover:text-white'
        }`}
      >
        <Monitor className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
