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
        sans: ['Barlow Semi Condensed', 'system-ui', 'sans-serif'],
        display: ['Spectral', 'Georgia', 'serif'],
      },
      // ACC's site is a flat Bootstrap-4 surface (0.25rem corners, 1px borders,
      // no elevation shadows) - reproduce that rather than a soft/shadowed style.
      borderRadius: { DEFAULT: '4px' },
      boxShadow: { card: 'none' },
    },
  },
  plugins: [],
}
