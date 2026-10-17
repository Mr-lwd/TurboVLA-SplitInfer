<script setup lang="ts">
import { useLocaleText } from './i18n'
const { t } = useLocaleText()

import { ref, computed } from 'vue'
import { withBase } from 'vitepress'
const mode = ref('comparison')
const playing = ref(false)
const modes = computed(() => [
  { id: 'comparison', label: t("All three modes") },
  { id: 'async', label: 'Async / replace' },
  { id: 'blend', label: 'Blend' },
  { id: 'sync', label: 'Sync' }
])
const source = computed(() => withBase(`/animations/pipeline-${mode.value}${playing.value ? '.gif' : '-poster.png'}`))
function select(id: string) { mode.value = id; playing.value = false }
</script>

<template>
  <section class="pipeline-player" :aria-label='t("Collaborative inference animations")'>
    <div class="mode-buttons">
      <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="select(item.id)">{{ item.label }}</button>
    </div>
    <div class="pipeline-image-scroll" tabindex="0" :aria-label='t("Pipeline canvas; scroll horizontally for detail")'>
      <img :key="source" :src="source" :alt="`${mode} ${t('pipeline: Thor inference and Orin execution, including initialization, stale-action trimming and blending')}`" width="1600" :height="mode === 'comparison' ? 1110 : 600">
    </div>
    <div class="player-actions">
      <button class="play-button" :aria-pressed="playing" @click="playing = !playing">{{ playing ? t("Stop animation") : t("Play animation") }}</button>
      <a :href="withBase(`/animations/pipeline-${mode}.gif`)" download>{{ t("Download GIF") }}</a>
      <a :href="withBase(`/animations/pipeline-${mode}-poster.png`)" target="_blank" rel="noopener">{{ t("View still frame") }}</a>
    </div>
    <p class="caption">{{ t("Click Play to animate. The shared illustrative timeline assumes two time units per prediction; it is not measured latency or speedup. Blended cells show old/new action indices, with new-action weights below. Async maps to replace in the code.") }}</p>
  </section>
</template>
