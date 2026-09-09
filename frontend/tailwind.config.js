/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        bg: {
          base: '#f8fafc',
          surface: '#ffffff',
          elevated: '#f1f5f9',
        },
        text: {
          DEFAULT: '#0f172a',
          primary: '#0f172a',
          secondary: '#334155', // High contrast Slate 700 (NOT washed out gray!)
          muted: '#475569',
        },
        primary: '#0f172a',
        secondary: '#334155',
        accent: {
          primary: '#2563eb',
          hover: '#1d4ed8',
          secondary: '#7c3aed',
        },
        border: {
          color: '#e2e8f0',
          DEFAULT: '#cbd5e1',
          strong: '#94a3b8',
        },
        status: {
          success: '#059669',
          warning: '#d97706',
          error: '#dc2626',
          info: '#0284c7',
        },
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        card: '0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        'card-hover': '0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)',
        modal: '0 20px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
}
