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
          base: '#000308',
          navy: '#001233',
          blue: '#00235e',
          card: 'rgba(0, 18, 51, 0.65)',
          card2: 'rgba(0, 12, 35, 0.85)',
          border: 'rgba(255, 255, 255, 0.10)',
          'border-glow': 'rgba(0, 110, 255, 0.45)',
          primary: '#ffffff',
          secondary: '#c9d1de',
          dim: '#7c8ba1',
          accent: '#006eff',
          cyan: '#006eff',
          green: '#34d399',
          amber: '#fbbf24',
          orange: '#fb923c',
          red: '#f87171',
          danger: '#ef4444',
          recovered: '#34d399',
        },
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Playfair Display', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 8px 32px rgba(0, 3, 8, 0.6)',
        'glow-cyan': '0 0 24px rgba(0, 110, 255, 0.35)',
        'glow-blue': '0 0 24px rgba(0, 110, 255, 0.4)',
        'glow-btn': '0 0 24px rgba(0, 110, 255, 0.45)',
        'glow-green': '0 0 20px rgba(52, 211, 153, 0.25)',
        'glow-red': '0 0 20px rgba(248, 113, 113, 0.3)',
      },
      borderRadius: {
        sm: '8px',
        md: '14px',
        lg: '20px',
        xl: '24px',
        '2xl': '28px',
        '3xl': '32px',
      },
    },
  },
  plugins: [],
};
