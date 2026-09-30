export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#002A54', ink: '#252525',
          bg: '#F5F8FA', card: '#FFFFFF', border: '#E2E7ED',
        },
        branddark: '#00172E',
        // One accent, used sparingly: active nav underline, CTAs, highlight icons.
        accent: '#C9A227',
        accentfill: '#F4C430',
        // Two status palettes per design-fidelity.md: saturated for chart fills,
        // darkened for small text (contrast at dashboard sizes).
        good: { DEFAULT: '#28A745', text: '#1E7E34' },
        warn: { DEFAULT: '#FFC107', text: '#B8860B' },
        bad: { DEFAULT: '#DC3545', text: '#BD2130' },
      },
      fontFamily: {
        sans: ['Fira Sans', 'system-ui', 'sans-serif'],
      },
      borderRadius: { DEFAULT: '6px' },
      boxShadow: { card: 'none' },
      transitionTimingFunction: {
        acc: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
}
