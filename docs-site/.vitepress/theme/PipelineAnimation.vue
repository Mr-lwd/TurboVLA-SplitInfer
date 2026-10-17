<script setup lang="ts">
import { ref, computed } from 'vue'
import { withBase } from 'vitepress'
const mode = ref('comparison')
const playing = ref(false)
const modes = [
  { id: 'comparison', label: '三模式对照' },
  { id: 'async', label: 'Async / replace' },
  { id: 'blend', label: 'Blend' },
  { id: 'sync', label: 'Sync' }
]
const source = computed(() => withBase(`/animations/pipeline-${mode.value}${playing.value ? '.gif' : '-poster.png'}`))
function select(id: string) { mode.value = id; playing.value = false }
</script>

<template>
  <section class="pipeline-player" aria-label="协同推理流水线动图">
    <div class="mode-buttons">
      <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="select(item.id)">{{ item.label }}</button>
    </div>
    <div class="pipeline-image-scroll" tabindex="0" aria-label="流水线画布，可横向滚动查看">
      <img :key="source" :src="source" :alt="`${mode} 流水线：Thor 推理与 Orin 执行，含初始化、过期裁剪与融合窗口`" width="1600" :height="mode === 'comparison' ? 1110 : 600">
    </div>
    <div class="player-actions">
      <button class="play-button" :aria-pressed="playing" @click="playing = !playing">{{ playing ? '停止并显示静态图' : '播放动图' }}</button>
      <a :href="withBase(`/animations/pipeline-${mode}.gif`)" download>下载当前 GIF</a>
      <a :href="withBase(`/animations/pipeline-${mode}-poster.png`)" target="_blank" rel="noopener">查看静态帧</a>
    </div>
    <p class="caption">动图默认静止，点击播放。统一示意时间轴，假设单次推理耗时 2 个单位；不代表实测延迟或加速比。融合格显示旧/新动作索引，格下为新动作权重。Async 对应代码中的 replace。</p>
  </section>
</template>
