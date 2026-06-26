/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Warm dark palette — Hyderabad office at night, lamp-lit interiors.
        nxt: {
          bg: '#12100e',
          surface: '#1c1814',
          panel: '#221e19',
          cabin: '#1a1510',
          desk: '#14110d',
          pantry: '#161310',
          wood: '#3d2b1f',
          woodlight: '#4a3528',
          lamp: '#f5a623',
          lampglow: 'rgba(245,166,35,0.13)',
          gold: '#f5c842',
          accent: '#e8854a',
          border: '#3d2b1f',
          text: '#f0e6d3',
          muted: '#8a7a6a',
          green: '#7cb87a',
          red: '#c47a6a',
          blue: '#7a9ab8',
          coffee: '#6b4226',
          // Legacy tokens — kept so any older component that hasn't been
          // refactored to the new names still renders.
          50: '#FFF8F0',
          100: '#FFEEDC',
          200: '#FFD9B0',
          400: '#FF9E4F',
          500: '#F77E2C',
          600: '#D85F12',
          700: '#A8460A',
        },
        ink: {
          50: '#F8F7F4',
          100: '#EFEDE7',
          200: '#D9D5CA',
          400: '#7A7464',
          600: '#403A2E',
          900: '#1F1B14',
        },
      },
      fontFamily: {
        display: ['"Fraunces"', 'Georgia', 'serif'],
        sans: ['"Inter"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.04), 0 8px 24px -6px rgba(0,0,0,0.45)',
        ticket: '0 0 0 1px rgba(232,133,74,0.25), 0 8px 28px -6px rgba(232,133,74,0.3)',
        gold: '0 0 0 1px rgba(245,200,66,0.35), 0 0 32px -4px rgba(245,200,66,0.45)',
        lamp: '0 0 64px 12px rgba(245,166,35,0.22)',
      },
      keyframes: {
        flicker: {
          '0%, 100%': { opacity: '0.92' },
          '50%': { opacity: '1' },
        },
        steamRise: {
          '0%': { transform: 'translateY(0) scale(1)', opacity: '0.5' },
          '100%': { transform: 'translateY(-60px) scale(1.6)', opacity: '0' },
        },
        walkBob: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-2px)' },
        },
        legLeft: {
          '0%, 100%': { transform: 'rotate(-18deg)' },
          '50%': { transform: 'rotate(18deg)' },
        },
        legRight: {
          '0%, 100%': { transform: 'rotate(18deg)' },
          '50%': { transform: 'rotate(-18deg)' },
        },
        armLeft: {
          '0%, 100%': { transform: 'rotate(12deg)' },
          '50%': { transform: 'rotate(-12deg)' },
        },
        armRight: {
          '0%, 100%': { transform: 'rotate(-12deg)' },
          '50%': { transform: 'rotate(12deg)' },
        },
      },
      animation: {
        flicker: 'flicker 2.4s ease-in-out infinite',
        steam: 'steamRise 2.6s ease-out infinite',
        walkBob: 'walkBob 0.36s ease-in-out infinite',
        legLeft: 'legLeft 0.36s ease-in-out infinite',
        legRight: 'legRight 0.36s ease-in-out infinite',
        armLeft: 'armLeft 0.36s ease-in-out infinite',
        armRight: 'armRight 0.36s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
