# TurboVLA documentation website

English and Simplified Chinese VitePress documentation with a white background, dark text and pale-blue accents. Use the language menu to switch the current page: English remains at `/`, with Chinese at `/zh/`. Navigation, local search and interactive components follow the selected language.

Maintain matching guide filenames in `guide/` and `zh/guide/`. Shared Vue components use `.vitepress/theme/i18n.ts` and `zh-CN.json`, and both languages read the same benchmark data. Figures, GIFs and editable PowerPoint use shared English scientific labels, avoiding duplicate media files. Generated benchmark tables remain on the English page; the Chinese page reads current metrics through the shared dashboard.

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
