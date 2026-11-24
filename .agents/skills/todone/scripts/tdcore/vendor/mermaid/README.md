# Offline Mermaid runtime for AUTODOC

This directory pins `mermaid@12.3.0` from npm.

- `mermaid.min.js` is the vendored JS SDK runtime (MIT).
- `render.cjs` is the local batch adapter used by `autodoc.py`.
- `dom-host.cjs` is a self-contained bundled DOM host derived from
  `linkedom@0.18.12`; generation does not require `node_modules` or a network.
- `package.json` and `package-lock.json` record the upstream package versions.

The adapter accepts JSON on stdin and returns a JSON map of diagram IDs to
Mermaid-generated SVG. It is deliberately not a hand-written SVG renderer:
Python supplies `AUTODOC-DIAGRAM-1` data and Mermaid owns layout and SVG output.
No CDN, browser fetch, external font, or external asset is used.
