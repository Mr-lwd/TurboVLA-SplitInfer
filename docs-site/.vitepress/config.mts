import { defineConfig } from 'vitepress'
import { repositoryAssets } from '../scripts/markdown-assets.mjs'

const base = process.env.DOCS_BASE || '/'
if (!base.startsWith('/') || !base.endsWith('/')) throw new Error('DOCS_BASE must start and end with /')

export default defineConfig({
  lang: 'zh-CN',
  title: 'TurboVLA',
  titleTemplate: ':title · SplitInfer',
  description: 'Jetson Orin Nano 8GB 与 Jetson Thor 128GB 双设备推理：架构、部署、调度与可复现验证。',
  base,
  appearance: false,
  lastUpdated: false,
  cleanUrls: false,
  markdown: { config: md => repositoryAssets(md, base) },
  srcExclude: ['README.md', 'DESIGN.md', 'qa/**'],
  head: [['meta', { name: 'theme-color', content: '#ffffff' }]],
  themeConfig: {
    siteTitle: 'TurboVLA / SplitInfer',
    nav: [{ text: '文档', link: '/' }, { text: '部署', link: '/guide/deployment' }, { text: '实测数据', link: '/guide/benchmark-results' }, { text: '验证', link: '/guide/validation' }],
    sidebar: [
      { text: '理解系统', items: [
        { text: '项目概览', link: '/' },
        { text: '双设备架构', link: '/guide/architecture' },
        { text: 'Sync / Blend / Async', link: '/guide/scheduling' }
      ] },
      { text: '运行与复现', items: [
        { text: '设备部署', link: '/guide/deployment' },
        { text: '配置速查', link: '/guide/configuration' },
        { text: '实测数据与对比', link: '/guide/benchmark-results' },
        { text: '数据口径与追加', link: '/guide/benchmark-data' },
        { text: '验证与结果', link: '/guide/validation' }
      ] },
      { text: '工程说明', items: [
        { text: '代码完整性', link: '/guide/completeness' },
        { text: '系统能力与边界', link: '/guide/capabilities' },
        { text: '故障排查', link: '/guide/troubleshooting' },
        { text: '文档网站部署', link: '/guide/site-deployment' }
      ] }
    ],
    outline: { level: [2, 3], label: '本页内容' },
    docFooter: { prev: '上一页', next: '下一页' },
    sidebarMenuLabel: '目录', returnToTopLabel: '返回顶部',
    darkModeSwitchLabel: '主题',
    search: { provider: 'local', options: { locales: { root: { translations: {
      button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
      modal: { noResultsText: '未找到相关内容', resetButtonTitle: '清空', footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } }
    } } } } }
  }
})
