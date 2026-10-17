import { copyFile, mkdir, readdir, unlink } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { siteAssets } from './site-assets.mjs'
const root = fileURLToPath(new URL('../../', import.meta.url))
// This directory contains generated copies only. Drop superseded benchmark
// exports so the next static release includes only the current comparison.
const benchmarkDir = path.join(root, 'docs-site/public/benchmarks')
await mkdir(benchmarkDir, { recursive: true })
const currentBenchmarks = new Set(siteAssets.map(([, target]) => target).filter(target => target.startsWith('benchmarks/')).map(target => path.basename(target)))
for (const entry of await readdir(benchmarkDir, { withFileTypes: true })) {
  if (entry.isFile() && !currentBenchmarks.has(entry.name)) await unlink(path.join(benchmarkDir, entry.name))
}
for (const [source, target] of siteAssets) {
  const destination = path.join(root, 'docs-site/public', target)
  await mkdir(path.dirname(destination), { recursive: true })
  await copyFile(path.join(root, source), destination)
}
console.log('Synced repository figures, deployment photographs and pipeline animations.')
