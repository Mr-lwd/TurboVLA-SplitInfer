import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import TimelineDemo from './TimelineDemo.vue'
import SystemOverview from './SystemOverview.vue'
import DeploymentGallery from './DeploymentGallery.vue'
import PipelineAnimation from './PipelineAnimation.vue'
import DiagramDownload from './DiagramDownload.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('TimelineDemo', TimelineDemo)
    app.component('SystemOverview', SystemOverview)
    app.component('DeploymentGallery', DeploymentGallery)
    app.component('PipelineAnimation', PipelineAnimation)
    app.component('DiagramDownload', DiagramDownload)
  }
} satisfies Theme
