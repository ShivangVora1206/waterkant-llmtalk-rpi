import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0f172a',
        panel: '#1e293b',
        border: '#334155',
      },
    },
  },
  plugins: [],
} satisfies Config
