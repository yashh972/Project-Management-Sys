/**
 * Bootstrap 3 sets `html { font-size: 10px }`, which would shrink every Tailwind `rem`
 * value to 62.5% of its intended size. Convert rem -> px (1rem = 16px) at build time so
 * Tailwind utilities render at their true size regardless of the root font size.
 */
const remToPx = () => ({
  postcssPlugin: 'rem-to-px',
  Declaration(decl) {
    if (decl.value.includes('rem')) {
      decl.value = decl.value.replace(/(-?\d*\.?\d+)rem\b/g, (_, n) => `${+(parseFloat(n) * 16).toFixed(3)}px`);
    }
  },
});
remToPx.postcss = true;

module.exports = { plugins: [remToPx] };
