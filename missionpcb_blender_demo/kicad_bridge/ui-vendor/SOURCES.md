# Vendored UI dependencies

## Motion 13.2.0

- Package: `motion@13.2.0` (MIT license; see `MOTION-LICENSE.md`).
- Official registry metadata: https://registry.npmjs.org/motion/13.2.0
- Downloaded package: https://registry.npmjs.org/motion/-/motion-13.2.0.tgz
- Upstream file: `package/dist/motion.js`, preserved without modification.
- Bundle SHA-256: `b24a0c29134800dad72021e22d5ead99fa941722526807f29c131f6fbffa5fe2`.
- Package SHA-512 integrity was checked against npm registry metadata before extraction.
- Official usage documentation: https://motion.dev/docs/quick-start

The UMD bundle exposes `window.Motion` in the browser. Serve this local file alongside the dashboard so animation does not require a runtime CDN request.

```html
<script src="ui-vendor/motion.js"></script>
<script>
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
    Motion.animate(".widget", { opacity: [0, 1], y: [8, 0] }, {
      duration: 0.24,
      delay: Motion.stagger(0.035),
      ease: "easeOut"
    });
  }
</script>
```
