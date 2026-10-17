import { defineConfig } from 'vitepress'
import { repositoryAssets } from '../scripts/markdown-assets.mjs'

const base = process.env.DOCS_BASE || '/'
if (!base.startsWith('/') || !base.endsWith('/')) throw new Error('DOCS_BASE must start and end with /')

export default defineConfig({
  lang: 'en-US',
  title: 'TurboVLA',
  titleTemplate: ':title · SplitInfer',
  description: 'Two-device inference on Jetson Orin Nano 8GB and Jetson Thor 128GB: architecture, deployment, scheduling and reproducible evaluation.',
  base,
  appearance: false,
  lastUpdated: false,
  cleanUrls: false,
  markdown: { config: md => repositoryAssets(md, base) },
  srcExclude: ['README.md', 'DESIGN.md', 'qa/**'],
  head: [['meta', { name: 'theme-color', content: '#ffffff' }]],
  themeConfig: {
    siteTitle: 'TurboVLA / SplitInfer',
    nav: [{ text: 'Docs', link: '/' }, { text: 'Deployment', link: '/guide/deployment' }, { text: 'Benchmarks', link: '/guide/benchmark-results' }, { text: 'Validation', link: '/guide/validation' }],
    sidebar: [
      { text: 'Understand the system', items: [
        { text: 'Overview', link: '/' },
        { text: 'Two-device architecture', link: '/guide/architecture' },
        { text: 'Sync / Blend / Async', link: '/guide/scheduling' }
      ] },
      { text: 'Run and reproduce', items: [
        { text: 'Device deployment', link: '/guide/deployment' },
        { text: 'Configuration', link: '/guide/configuration' },
        { text: 'Benchmark results', link: '/guide/benchmark-results' },
        { text: 'Data and methodology', link: '/guide/benchmark-data' },
        { text: 'Validation', link: '/guide/validation' }
      ] },
      { text: 'Engineering', items: [
        { text: 'Code coverage', link: '/guide/completeness' },
        { text: 'System capabilities', link: '/guide/capabilities' },
        { text: 'Troubleshooting', link: '/guide/troubleshooting' },
        { text: 'Website deployment', link: '/guide/site-deployment' }
      ] }
    ],
    outline: { level: [2, 3], label: 'On this page' },
    docFooter: { prev: 'Previous page', next: 'Next page' },
    sidebarMenuLabel: 'Menu', returnToTopLabel: 'Back to top',
    darkModeSwitchLabel: 'Theme',
    search: { provider: 'local', options: { locales: { root: { translations: {
      button: { buttonText: 'Search docs', buttonAriaLabel: 'Search docs' },
      modal: { noResultsText: 'No results found', resetButtonTitle: 'Clear', footer: { selectText: 'Select', navigateText: 'Navigate', closeText: 'Close' } }
    } } } } }
  }
})
