import { readFile, readdir, access } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = fileURLToPath(new URL('../', import.meta.url))
async function markdown(dir) {
  const result = []
  for (const item of await readdir(dir, { withFileTypes: true })) {
    if (item.name.startsWith('.') || ['node_modules', 'public', 'qa'].includes(item.name)) continue
    const full = path.join(dir, item.name)
    if (item.isDirectory()) result.push(...await markdown(full))
    else if (item.name.endsWith('.md') && item.name !== 'README.md' && item.name !== 'DESIGN.md') result.push(full)
  }
  return result
}
const errors = []
const pages = await markdown(root)
for (const file of pages) {
  const body = await readFile(file, 'utf8')
  if (!/^# /m.test(body)) errors.push(`${file}: missing h1`)
  for (const match of body.matchAll(/\]\(([^)]+)\)/g)) {
    const link = match[1].split('#')[0]
    if (!link || /^(https?:|mailto:)/.test(link)) continue
    const target = link.startsWith('/') ? path.join(root, 'public', link) : path.resolve(path.dirname(file), link)
    try { await access(target) } catch { errors.push(`${file}: broken link ${link}`) }
  }
}
if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1 }
else console.log(`${pages.length} documentation pages: local Markdown links and headings OK.`)
