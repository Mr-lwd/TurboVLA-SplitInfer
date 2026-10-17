# TurboVLA 文档网站

独立 VitePress 站点，黑字、白底、浅蓝；左侧目录、右侧正文、本页目录、本地搜索与可操作的三模式调度示例。

```bash
cd docs-site
npm ci
npm run dev
# 发布前
npm run check
npm run build
npm run preview
```

Node.js ≥22。构建目录 `.vitepress/dist/`，可部署至任意静态服务器。

子路径：Linux 使用 `DOCS_BASE=/turbovla/ npm run build`；PowerShell 先 `$env:DOCS_BASE='/turbovla/'`。详细部署见 [guide/site-deployment.md](guide/site-deployment.md)。

本地依赖、构建缓存与 QA 截图不提交 Git；`package-lock.json` 保留以便复现。架构图、流水线图与动图、可编辑 PPT、实拍整理图和原图均通过 `scripts/sync-assets.mjs` 从仓库复制，避免手工维护两份。实拍整理图保留 AI 清理说明与原图入口。

Markdown 的图片与下载链接统一指向仓库 `assets/` 的相对路径，可在 GitHub 直接查看。网站构建通过 `scripts/site-assets.mjs` 的资源清单映射到部署路径，并支持 `DOCS_BASE` 子目录。交互组件配有 GitHub 可见的图片、GIF 或表格内容。`npm run check` 扫描整个仓库的 Markdown，检查本地引用、文件名大小写与资源是否被 Git 忽略；无需预先生成 `public/`。

依赖维护：保留 VitePress 1.6.4 稳定主题，Vue 固定为 3.5.44，构建工具覆盖至 Vite 6.4.4，以修复旧依赖的已知问题；静态构建及本地预览已检查，npm audit 为 0 项。以后更新时保留锁文件并重新验证构建、搜索和子路径。

模板来源：VitePress 默认主题（MIT）；设计参考 Taste Skill 的 `product-performs` 方向，技术文档约束优先。详见 [DESIGN.md](DESIGN.md)。
