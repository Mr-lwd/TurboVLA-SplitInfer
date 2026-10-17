<script setup lang="ts">
import { useLocaleText } from './i18n'
const { t, isZh } = useLocaleText()

import { computed, ref } from 'vue'
const mode = ref('blend')
const delay = ref(2)
const modes = [{ id: 'sync', name: 'Sync' }, { id: 'blend', name: 'Blend' }, { id: 'replace', name: 'Async / replace' }]
const observation = computed(() => mode.value === 'sync' ? 12 : 4)
const arrival = computed(() => observation.value + delay.value)
const labels = computed(() => Array.from({ length: 20 }, (_, i) => {
  if (mode.value === 'sync') {
    if (i < 12) return { kind: 'old', text: `A${i}` }
    if (i < arrival.value) return { kind: 'wait', text: t("Wait") }
    return { kind: 'new', text: `B${i - arrival.value}` }
  }
  if (i < arrival.value) return { kind: i < 12 ? 'old' : 'hold', text: i < 12 ? `A${i}` : 'H' }
  if (delay.value >= 12 || i >= 16) return { kind: i < 12 ? 'old' : 'hold', text: i < 12 ? `A${i}` : 'H' }
  const overlap = Math.min(3, Math.max(0, 12 - arrival.value), 12 - delay.value)
  if (mode.value === 'blend' && i < arrival.value + overlap) {
    return { kind: 'blend', text: `${i - arrival.value + 1}/${overlap}` }
  }
  return { kind: 'new', text: `B${i - 4}` }
}))
const explanation = computed(() => {
  if (mode.value === 'sync') return (isZh.value ? `A 块执行完毕后请求 B，等待期间不推进环境控制步；收到后从 B0 开始执行。` : `Request B after exhausting A. Control steps pause while waiting, then resume from B0.`)
  if (delay.value >= 12) return (isZh.value ? `在控制步 4 采样的 B 块已完全过期，整块丢弃；当前示例不展示下一次请求。` : `Chunk B, sampled at control step 4, is entirely stale and is discarded. This example does not show the next request.`)
  const overlap = Math.min(3, Math.max(0, 12 - arrival.value), 12 - delay.value)
  const alignment = isZh.value
    ? `控制步 4 采样，在步 ${arrival.value} 合并，裁掉 B 的前 ${delay.value} 步。`
    : `Sample at step 4 and merge at step ${arrival.value}; discard the first ${delay.value} actions of B. `
  return alignment + (mode.value === 'blend' && overlap
    ? (isZh.value ? `剩余重叠窗口为 ${overlap} 步，只融合前六维；夹爪离散切换。` : `The remaining overlap is ${overlap} steps. Blend six pose dimensions; switch the gripper discretely.`)
    : t('New actions replace the future timeline.'))
})
</script>

<template>
  <div class="timeline-demo" data-ui>
    <div class="mode-buttons" role="group" :aria-label='t("Choose scheduling mode")'>
      <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="mode = item.id">{{ item.name }}</button>
    </div>
    <label for="delay">{{ mode === 'sync' ? t("Illustrative waiting slots") : t("Control steps executed during the request") }} <strong>{{ delay }}</strong></label>
    <input id="delay" v-model.number="delay" type="range" min="1" max="12" step="1" />
    <div class="timeline-scroll" tabindex="0" :aria-label='t("Action timeline; scroll horizontally")'>
      <div class="timeline-row"><b>Thor</b><div class="slots"><span v-for="(_, i) in labels" :key="i" :class="i >= observation && i < arrival ? 'infer' : 'idle'">{{ i === observation ? t("Req B") : i > observation && i < arrival ? t("Infer") : '·' }}</span></div></div>
      <div class="timeline-row"><b>Orin</b><div class="slots"><span v-for="(slot, i) in labels" :key="i" :class="slot.kind">{{ slot.text }}</span></div></div>
    </div>
    <p class="demo-explanation" aria-live="polite">{{ explanation }}</p>
    <div class="legend"><span class="old">{{ t("Old chunk A") }}</span><span class="new">{{ t("New chunk B") }}</span><span class="blend">{{ t("Blend weight") }}</span><span class="hold">H = hold</span></div>
    <p class="caption">{{ t("Mechanism example: H=12, R=4, B=3; one replanning event, omitting the initial wait shared by all modes. Sync waiting slots represent wall time; Async/Blend slots represent executed control steps. Slot width is not measured duration.") }}</p>
    <noscript>{{ t("Enable JavaScript for this interactive example. The text below explains all modes and alignment rules.") }}</noscript>
  </div>
</template>
