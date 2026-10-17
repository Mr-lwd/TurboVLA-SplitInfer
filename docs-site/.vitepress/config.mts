import { defineConfig } from 'vitepress'
import { repositoryAssets } from '../scripts/markdown-assets.mjs'
import chinese from './theme/zh-CN.json'

const base = process.env.DOCS_BASE || '/'
if (!base.startsWith('/') || !base.endsWith('/')) throw new Error('DOCS_BASE must start and end with /')

const english = defineConfig({
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

const translate = (text: string) => (chinese as Record<string, string>)[text] ?? text
const zhLink = (link: string) => `/zh${link}`
const theme = english.themeConfig!

export default defineConfig({
  ...english,
  locales: {
    root: { label: 'English', lang: 'en-US', link: '/' },
    zh: {
      label: '简体中文', lang: 'zh-CN', link: '/zh/',
      description: '具身智能 VLA 模型的双设备协同推理：Jetson Orin Nano 8GB 与 Thor 128GB 的架构、部署、调度及实测结果。',
      themeConfig: {
        nav: theme.nav!.map(item => ({ ...item, text: translate(item.text), link: zhLink(item.link!) })),
        sidebar: (theme.sidebar as any[]).map(section => ({
          ...section, text: translate(section.text),
          items: section.items.map((item: { text: string; link: string }) => ({ text: translate(item.text), link: zhLink(item.link) }))
        })),
        outline: { level: [2, 3], label: '本页内容' },
        docFooter: { prev: '上一页', next: '下一页' },
        sidebarMenuLabel: '目录', returnToTopLabel: '返回顶部',
        langMenuLabel: '切换语言',
      }
    }
  },
  themeConfig: {
    ...theme,
    langMenuLabel: 'Change language',
    search: { provider: 'local', options: { locales: {
      root: { translations: {
        button: { buttonText: 'Search docs', buttonAriaLabel: 'Search docs' },
        modal: { noResultsText: 'No results found', resetButtonTitle: 'Clear', footer: { selectText: 'Select', navigateText: 'Navigate', closeText: 'Close' } }
      } },
      zh: { translations: {
        button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
        modal: { noResultsText: '未找到相关内容', resetButtonTitle: '清空', footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } }
      } }
    } } }
  }
})
