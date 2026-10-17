// Repository sources are authoritative; public/ is generated for website hosting.
export const siteAssets = [
  ['assets/figures/architecture-overview.png', 'figures/architecture-overview.png'],
  ...['framework-flat.png', 'pipeline-flat.png'].map(file => [`assets/diagrams/split-inference/${file}`, `figures/${file}`]),
  ['assets/diagrams/split-inference/turbovla-diagrams-editable.pptx', 'downloads/turbovla-diagrams-editable.pptx'],
  ...['orin', 'thor'].map(name => [`assets/realpics/cleaned/${name}-clean.jpg`, `realpics/${name}-clean.jpg`]),
  ['assets/realpics/orin.jpg', 'realpics/orin-original.jpg'],
  ['assets/realpics/Thor.jpg', 'realpics/thor-original.jpg'],
  ...['comparison', 'async', 'blend', 'sync'].flatMap(name =>
    ['.gif', '-poster.png'].map(suffix => [`assets/diagrams/split-inference/animations/pipeline-${name}${suffix}`, `animations/pipeline-${name}${suffix}`]))
]
