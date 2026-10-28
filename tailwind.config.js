/**
 * Tailwind runs alongside Bootstrap 3, so it is configured to stay out of its way:
 *  - preflight is off (no global reset, Bootstrap keeps owning base styles)
 *  - every utility is prefixed `tw-` (e.g. `tw-flex`), so nothing collides with
 *    Bootstrap classes such as `.hidden`, `.row`, `.collapse` or `.container`
 *  - colours, radii, fonts and shadows point at the CSS variables in css/modern.css,
 *    so utilities and the component layer always share one design system
 */
module.exports = {
  prefix: 'tw-',
  important: false,
  corePlugins: { preflight: false },
  content: ['./app/view/**/*.html', './js/global.js'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: { DEFAULT: 'var(--surface)', 2: 'var(--surface-2)', 3: 'var(--surface-3)' },
        line: { DEFAULT: 'var(--border)', strong: 'var(--border-strong)' },
        ink: { DEFAULT: 'var(--text)', 2: 'var(--text-2)', 3: 'var(--text-3)' },
        accent: { DEFAULT: 'var(--accent)', strong: 'var(--accent-strong)', soft: 'var(--accent-soft)', ink: 'var(--accent-ink)' },
        success: { DEFAULT: 'var(--success)', soft: 'var(--success-soft)' },
        warning: { DEFAULT: 'var(--warning)', soft: 'var(--warning-soft)' },
        danger: { DEFAULT: 'var(--danger)', soft: 'var(--danger-soft)' },
        info: { DEFAULT: 'var(--info)', soft: 'var(--info-soft)' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      borderRadius: { sm: 'var(--radius-sm)', DEFAULT: 'var(--radius)', lg: 'var(--radius-lg)' },
      boxShadow: { card: 'var(--shadow-sm)', pop: 'var(--shadow-md)' },
    },
  },
};
