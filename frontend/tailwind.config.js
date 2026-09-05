/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: '#667eea',
        highlight: '#764ba2',
        success: '#00b894',
        warning: '#e9b949',
        danger: '#e17055',
        app: 'var(--bg)',
        card: 'var(--card)',
        'card-muted': 'var(--card-muted)',
        ink: 'var(--text)',
        muted: 'var(--muted)',
        line: 'var(--border)',
        nav: 'var(--nav)',
        primary: 'var(--text)',
        secondary: 'var(--card-muted)',
        light: 'var(--bg)',
        text: 'var(--text)',
        textLight: 'var(--muted)',
        border: 'var(--border)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '6px',
      },
      boxShadow: {
        'card': 'var(--shadow)',
        'card-hover': 'var(--shadow-hover)',
        'nav': 'var(--shadow-nav)',
      },
      animation: {
        'fade-in': 'fadeIn 0.45s ease-out',
        'slide-up': 'slideUp 0.45s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
