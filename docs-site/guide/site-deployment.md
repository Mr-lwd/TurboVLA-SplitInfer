# Website deployment

The documentation is an independent VitePress static site under `docs-site/`. Deploy only its build output. It neither starts the inference server nor requires that server to be publicly accessible.

## Local preview

Use Node.js 22 or newer:

```bash
cd docs-site
npm ci
npm run dev
```

Open the printed address, normally `http://127.0.0.1:5173`. Local search needs no service key.

## Build and check

```bash
npm run check
npm run build
npm run preview
```

The build synchronizes repository media automatically. Output is in `docs-site/.vitepress/dist/`; preview uses port 4173. Generated public assets, caches, QA output and dependencies are ignored by Git.

## Hosting under a subpath

For `https://example.com/turbovla/`, set a base with both leading and trailing slashes:

::: code-group
```bash [Linux / macOS]
DOCS_BASE=/turbovla/ npm run build
```
```powershell [PowerShell]
$env:DOCS_BASE = '/turbovla/'
npm run build
```
:::

Use the default `/` for a domain root. Rebuild after changing the base.

## Static hosting

Copy the contents of `.vitepress/dist/` to `/var/www/html/turbovla/`. Merge the following location into an existing Nginx server configuration:

```nginx
location /turbovla/ {
    root /var/www/html;
    index index.html;
    try_files $uri $uri/ =404;
}
```

The site uses `.html` routes and does not need an SPA fallback. Domain routing, TLS and existing server blocks remain part of the hosting configuration. The serving host needs no Node or Python runtime when only static files are deployed.

Upload static output only, excluding models, datasets, evaluation outputs, API configuration and Python environments.

## Content locations

| Content | File |
| --- | --- |
| Homepage | `docs-site/index.md` |
| Guides | `docs-site/guide/*.md` |
| Navigation, search and base | `docs-site/.vitepress/config.mts` |
| Typography and responsive layout | `docs-site/.vitepress/theme/style.css` |
| Interactive scheduling | `docs-site/.vitepress/theme/TimelineDemo.vue` |

## Open-source foundations

The site uses the [VitePress](https://github.com/vuejs/vitepress) default theme (MIT), including its [sidebar](https://vitepress.dev/reference/default-theme-sidebar), [local search](https://vitepress.dev/reference/default-theme-search) and [deployment workflow](https://vitepress.dev/guide/deploy). The layout was reviewed using [Taste Skill](https://github.com/Leonxlnx/taste-skill), adapted to concise technical documentation.
