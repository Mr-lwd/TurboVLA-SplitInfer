import { readFile, stat } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createMarkdownRenderer } from 'vitepress'
import { siteAssets } from './site-assets.mjs'

const root = fileURLToPath(new URL('../../', import.meta.url))
const files = new Set(execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean))
const pages = [...files].filter(file => /\.mdx?$/.test(file))
const parser = await createMarkdownRenderer(root)
const errors = []
let localLinks = 0

async function checkLink(file, url) {
  if (!url || /^(?:[a-z]+:|\/\/|#)/i.test(url)) return
  localLinks++
  if (url.startsWith('/')) {
    errors.push(`${file}: site-only URL ${url}; use a repository-relative path for GitHub`)
    return
  }
  const target = path.resolve(root, path.dirname(file), decodeURIComponent(url.split(/[?#]/)[0]))
  const relative = path.relative(root, target).split(path.sep).join('/')
  if (relative.startsWith('../') || path.isAbsolute(relative)) {
    errors.push(`${file}: link outside repository ${url}`)
    return
  }
  try {
    const info = await stat(target)
    const included = info.isDirectory() ? [...files].some(entry => entry.startsWith(`${relative}/`)) : files.has(relative)
    if (!included) errors.push(`${file}: ignored/unpublished target or wrong case ${url}`)
  } catch { errors.push(`${file}: missing target ${url}`) }
}

async function visit(tokens, file) {
  for (const token of tokens) {
    if (token.type === 'image') await checkLink(file, token.attrGet('src'))
    if (token.type === 'link_open') await checkLink(file, token.attrGet('href'))
    if (token.type === 'html_block' || token.type === 'html_inline') {
      for (const match of token.content.matchAll(/\b(?:src|href)\s*=\s*["']([^"']+)["']/g)) await checkLink(file, match[1])
    }
    if (token.children) await visit(token.children, file)
  }
}

for (const file of pages) {
  const body = await readFile(path.join(root, file), 'utf8')
  if (!/^# /m.test(body)) errors.push(`${file}: missing h1`)
  await visit(parser.parse(body, {}), file)
}
// Check source assets, not ignored public copies: this also works in a fresh clone.
for (const [source] of siteAssets) await checkLink('README.md', source)
if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1 }
else console.log(`${pages.length} repository Markdown files, ${localLinks} local references and ${siteAssets.length} website assets: OK (GitHub paths, filename case, source availability).`)
