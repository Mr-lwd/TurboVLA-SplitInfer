import { readdir, readFile } from 'node:fs/promises'
import assert from 'node:assert/strict'

const english = (await readdir(new URL('../guide/', import.meta.url))).filter(name => name.endsWith('.md')).sort()
const chinese = (await readdir(new URL('../zh/guide/', import.meta.url))).filter(name => name.endsWith('.md')).sort()
assert.deepEqual(chinese, english, 'Every guide must have a matching Chinese and English route')
for (const page of ['index.md', ...english.map(name => `guide/${name}`)]) {
  const en = await readFile(new URL(`../${page}`, import.meta.url), 'utf8')
  const zh = await readFile(new URL(`../zh/${page}`, import.meta.url), 'utf8')
  assert.match(zh, /[\u3400-\u9fff]/, `Missing Chinese content: ${page}`)
  const components = text => [...text.matchAll(/<(SystemOverview|DeploymentGallery|DiagramDownload|PipelineAnimation|TimelineDemo|BenchmarkDashboard)\b/g)].map(match => match[1]).sort()
  assert.deepEqual(components(zh), components(en), `Locale component mismatch: ${page}`)
}
console.log(`${english.length + 1} matching bilingual routes and shared component placements: OK.`)
