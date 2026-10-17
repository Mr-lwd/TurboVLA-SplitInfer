import { readFileSync } from 'node:fs'
const catalog = JSON.parse(readFileSync(new URL('../../reports/evaluation/catalog.json', import.meta.url), 'utf8'))
// Repository sources are authoritative; public/ is generated for website hosting.
export const siteAssets = [
  ['reports/evaluation/catalog.json', 'benchmarks/catalog.json'],
  ['reports/evaluation/summary.csv', 'benchmarks/summary.csv'],
  ...catalog.groups.flatMap(group => ['svg', 'png'].map(ext =>
    [`assets/benchmarks/${group.id}.${ext}`, `benchmarks/${group.id}.${ext}`])),
  ...catalog.groups.filter(group => group.run_ids.some(id => catalog.runs.find(run => run.id === id)
    .records.some(record => record.metrics.remote_stage_timings))).flatMap(group => ['svg', 'png'].map(ext =>
    [`assets/benchmarks/${group.id}-stages.${ext}`, `benchmarks/${group.id}-stages.${ext}`])),
  ['assets/figures/architecture-overview.png', 'figures/architecture-overview.png'],
  ...['framework-flat.png', 'pipeline-flat.png'].map(file => [`assets/diagrams/split-inference/${file}`, `figures/${file}`]),
  ['assets/diagrams/split-inference/turbovla-diagrams-editable.pptx', 'downloads/turbovla-diagrams-editable.pptx'],
  ...['orin', 'thor'].map(name => [`assets/realpics/cleaned/${name}-clean.jpg`, `realpics/${name}-clean.jpg`]),
  ['assets/realpics/orin.jpg', 'realpics/orin-original.jpg'],
  ['assets/realpics/Thor.jpg', 'realpics/thor-original.jpg'],
  ...['comparison', 'async', 'blend', 'sync'].flatMap(name =>
    ['.gif', '-poster.png'].map(suffix => [`assets/diagrams/split-inference/animations/pipeline-${name}${suffix}`, `animations/pipeline-${name}${suffix}`]))
]
