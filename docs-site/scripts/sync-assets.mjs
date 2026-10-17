import { copyFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = fileURLToPath(new URL('../../', import.meta.url))
const destination = path.join(root, 'docs-site/public/figures')
await mkdir(destination, { recursive: true })
await copyFile(path.join(root, 'assets/figures/architecture-overview.png'), path.join(destination, 'architecture-overview.png'))
for (const file of ['framework-flat.png', 'pipeline-flat.png']) {
  await copyFile(path.join(root, `assets/diagrams/split-inference/${file}`), path.join(destination, file))
}
const downloadDir = path.join(root, 'docs-site/public/downloads')
await mkdir(downloadDir, { recursive: true })
await copyFile(path.join(root, 'assets/diagrams/split-inference/turbovla-diagrams-editable.pptx'), path.join(downloadDir, 'turbovla-diagrams-editable.pptx'))
const photoDir = path.join(root, 'docs-site/public/realpics')
const animationDir = path.join(root, 'docs-site/public/animations')
await mkdir(photoDir, { recursive: true })
await mkdir(animationDir, { recursive: true })
for (const name of ['orin', 'thor']) {
  await copyFile(path.join(root, `assets/realpics/cleaned/${name}-clean.jpg`), path.join(photoDir, `${name}-clean.jpg`))
}
await copyFile(path.join(root, 'assets/realpics/orin.jpg'), path.join(photoDir, 'orin-original.jpg'))
await copyFile(path.join(root, 'assets/realpics/Thor.jpg'), path.join(photoDir, 'thor-original.jpg'))
for (const name of ['comparison', 'async', 'blend', 'sync']) {
  for (const suffix of ['.gif', '-poster.png']) {
    const file = `pipeline-${name}${suffix}`
    await copyFile(path.join(root, `assets/diagrams/split-inference/animations/${file}`), path.join(animationDir, file))
  }
}
console.log('Synced repository figures, deployment photographs and pipeline animations.')
