/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg:       '#0A0E1A',
          surface:  '#111827',
          card:     '#1A2235',
          border:   '#243049',
          accent:   '#00D4FF',
          green:    '#00FF88',
          red:      '#FF3B5C',
          yellow:   '#FFB800',
          text:     '#E2E8F0',
          muted:    '#64748B',
        }
      },
      fontFamily: {
        mono:    ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Syne', 'sans-serif'],
        body:    ['DM Sans', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink':      'blink 1.2s step-end infinite',
        'slide-up':   'slideUp 0.4s ease-out',
        'fade-in':    'fadeIn 0.3s ease-out',
      },
      keyframes: {
        blink:   { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(16px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
      },
    },
  },
  plugins: [],
}
