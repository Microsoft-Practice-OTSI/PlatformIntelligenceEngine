/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0f111a',
          surface: '#181b26',
          elevated: '#242838',
        },
        text: {
          primary: '#e2e8f0',
          secondary: '#94a3b8',
        },
        accent: {
          primary: '#6366f1',
          hover: '#4f46e5',
          secondary: '#8b5cf6',
        },
        border: {
          color: '#2e3347'
        },
        status: {
          success: '#10b981',
          warning: '#f59e0b',
          error: '#ef4444',
          info: '#3b82f6',
        },
      }
    },
  },
  plugins: [],
}
