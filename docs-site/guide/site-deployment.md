# 文档网站部署

本站是独立的 VitePress 静态文档，源码在项目根目录的 `docs-site/`，部署时只需上传构建产物。推理服务不由网站启动，也不需要发布到公网。

## 本地预览

要求 Node.js 22 或更新版本。在项目根目录执行：

```bash
cd docs-site
npm ci
npm run dev
```

打开终端输出的本地地址，默认 `http://127.0.0.1:5173`。站点使用本地搜索，无需搜索服务密钥。

## 构建与检查

```bash
npm run check
npm run build
npm run preview
```

`build` 自动同步仓库原始架构图。产物位于 `docs-site/.vitepress/dist/`；`preview` 默认端口 4173。

## 部署到子路径

若目标是 `https://example.com/turbovla/`，构建时设置 base，必须有首尾 `/`：

::: code-group
```bash [Linux / macOS]
DOCS_BASE=/turbovla/ npm run build
```
```powershell [PowerShell]
$env:DOCS_BASE = '/turbovla/'
npm run build
```
:::

若部署到域名根目录，使用默认 `/`。修改 base 后重新构建；不要仅搬动旧产物而保留错误的资源前缀。

## 云服务器静态托管

将 `.vitepress/dist/` 的全部内容复制到 `/var/www/html/turbovla/`。以已有 Nginx 站点为例，将此 location 合并到你的 server 配置中：

```nginx
location /turbovla/ {
    root /var/www/html;
    index index.html;
    try_files $uri $uri/ =404;
}
```

本站保留 `.html` 路由，无需 SPA fallback。域名、HTTPS 证书及现有 server 块由你的服务器配置管理；这里不会替换已有网站。

只上传静态产物，不上传模型、数据、评测输出、API 配置或 Python 环境。服务器端无需 Node 或 Python。

## 修改内容

| 需要修改 | 文件 |
| --- | --- |
| 首页 | `docs-site/index.md` |
| 文档正文 | `docs-site/guide/*.md` |
| 左侧导航、搜索、base | `docs-site/.vitepress/config.mts` |
| 颜色、字体、响应式布局 | `docs-site/.vitepress/theme/style.css` |
| 交互调度示例 | `docs-site/.vitepress/theme/TimelineDemo.vue` |

## 开源来源

网站基于 [VitePress](https://github.com/vuejs/vitepress) 默认文档主题（MIT），采用其[侧边栏](https://vitepress.dev/reference/default-theme-sidebar)与[本地搜索](https://vitepress.dev/reference/default-theme-search)能力。部署方式参考 [VitePress 部署文档](https://vitepress.dev/guide/deploy)。版式使用 [Taste Skill](https://github.com/Leonxlnx/taste-skill) 的设计审查方法，按本项目的紧凑技术文档需求调整。
