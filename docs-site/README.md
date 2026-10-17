# TurboVLA documentation website

English VitePress documentation with a white background, dark text and pale-blue accents. Features include sidebar navigation, local search, interactive scheduling, benchmark exploration and deployment media.

```bash
cd docs-site
npm ci
npm run dev
# Before publication:
npm run check
npm run build
npm run preview
```

Requires Node.js 22 or newer. Deploy `.vitepress/dist/` to a static host. Set `DOCS_BASE=/turbovla/` when hosting under a subpath; see the [deployment guide](guide/site-deployment.md).

Repository `assets/` files are authoritative. `scripts/site-assets.mjs` maps them to generated `public/` paths; `scripts/sync-assets.mjs` copies them for builds. Markdown uses repository-relative asset links so it also works on GitHub. Keep `package-lock.json`; do not commit dependencies, generated copies, build output or QA files.

The [benchmark page](guide/benchmark-results.md) reads [latest.json](../reports/evaluation/latest.json). Use the [data workflow](guide/benchmark-data.md) to update results and regenerate English charts and tables. A website build needs no GPU or original evaluation outputs.

`npm run check` scans repository Markdown for valid local references, filename case and Git availability. Test search, interactive controls and subpath routing after dependency or content updates.

Built on the VitePress default theme (MIT). See [design notes](DESIGN.md) for visual conventions and asset provenance.
