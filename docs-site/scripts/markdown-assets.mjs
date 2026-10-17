import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { siteAssets } from './site-assets.mjs'

const repoRoot = fileURLToPath(new URL('../../', import.meta.url))
const publicPaths = new Map(siteAssets.map(([source, target]) => [path.resolve(repoRoot, source), target]))

// Markdown keeps repository-relative URLs for GitHub. Only the website renderer
// maps known assets to copied public files, including deployments under a base path.
export function repositoryAssets(md, base) {
  for (const [rule, attribute] of [['image', 'src'], ['link_open', 'href']]) {
    const original = md.renderer.rules[rule]
    md.renderer.rules[rule] = (tokens, index, options, env, renderer) => {
      const token = tokens[index]
      const url = token.attrGet(attribute)
      if (env.path && url && !/^(?:[a-z]+:|\/|#)/i.test(url)) {
        const [pathname, suffix = ''] = url.split(/(?=[?#])/, 2)
        const target = publicPaths.get(path.resolve(path.dirname(env.path), decodeURIComponent(pathname)))
        if (target) {
          if (rule === 'image') token.attrSet(attribute, `/${target}${suffix}`)
          else {
            token.attrSet(attribute, `${base}${target}${suffix}`)
            if (target.endsWith('.pptx')) token.attrSet('download', '')
            return renderer.renderToken(tokens, index, options)
          }
        }
      }
      return original ? original(tokens, index, options, env, renderer) : renderer.renderToken(tokens, index, options)
    }
  }
}
