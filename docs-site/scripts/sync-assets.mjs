import { copyFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { siteAssets } from './site-assets.mjs'
const root = fileURLToPath(new URL('../../', import.meta.url))
for (const [source, target] of siteAssets) {
  const destination = path.join(root, 'docs-site/public', target)
  await mkdir(path.dirname(destination), { recursive: true })
  await copyFile(path.join(root, source), destination)
}
console.log('Synced repository figures, deployment photographs and pipeline animations.')
