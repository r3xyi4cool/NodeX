// Tailwind CSS configuration for NodeX Dashboard 2 matching Dashboard 1 tokens
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        nodex: {
          base: '#0a0f1e',
          card: '#111827',
          card2: '#1a2235',
          border: 'rgba(99, 179, 237, 0.12)',
          'border-glow': 'rgba(99, 179, 237, 0.35)',
          primary: '#e2e8f0',
          secondary: '#94a3b8',
          dim: '#4a5568',
          cyan: '#22d3ee',
          green: '#4ade80',
          amber: '#fbbf24',
          orange: '#fb923c',
          red: '#f87171',
          danger: '#ef4444',
          recovered: '#34d399',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 4px 24px rgba(0, 0, 0, 0.4)',
        'glow-cyan': '0 0 20px rgba(34, 211, 238, 0.2)',
        'glow-green': '0 0 20px rgba(74, 222, 128, 0.25)',
        'glow-red': '0 0 20px rgba(248, 113, 113, 0.3)',
      },
      borderRadius: {
        sm: '6px',
        md: '12px',
        lg: '18px',
        xl: '20px',
      },
    },
  },
  plugins: [],
};
