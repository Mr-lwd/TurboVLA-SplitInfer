<script setup lang="ts">
import { computed, ref } from 'vue'
const mode = ref('blend')
const delay = ref(2)
const modes = [{ id: 'sync', name: 'Sync' }, { id: 'blend', name: 'Blend' }, { id: 'replace', name: 'Async / replace' }]
const observation = computed(() => mode.value === 'sync' ? 12 : 4)
const arrival = computed(() => observation.value + delay.value)
const labels = computed(() => Array.from({ length: 20 }, (_, i) => {
  if (mode.value === 'sync') {
    if (i < 12) return { kind: 'old', text: `A${i}` }
    if (i < arrival.value) return { kind: 'wait', text: '等待' }
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
  if (mode.value === 'sync') return `A 块执行完毕后请求 B，等待期间不推进环境控制步；收到后从 B0 开始执行。`
  if (delay.value >= 12) return `在控制步 4 采样的 B 块已完全过期，整块丢弃；当前示例不展示下一次请求。`
  const overlap = Math.min(3, Math.max(0, 12 - arrival.value), 12 - delay.value)
  return `控制步 4 采样，在步 ${arrival.value} 合并，裁掉 B 的前 ${delay.value} 步。${mode.value === 'blend' && overlap ? `剩余重叠窗口为 ${overlap} 步，只融合前六维；夹爪离散切换。` : '新动作替换未来时间线。'}`
})
</script>

<template>
  <div class="timeline-demo" data-ui>
    <div class="mode-buttons" role="group" aria-label="选择调度模式">
      <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="mode = item.id">{{ item.name }}</button>
    </div>
    <label for="delay">{{ mode === 'sync' ? '示意等待槽数' : '请求期间执行的控制步数' }} <strong>{{ delay }}</strong></label>
    <input id="delay" v-model.number="delay" type="range" min="1" max="12" step="1" />
    <div class="timeline-scroll" tabindex="0" aria-label="动作时间线，可横向滚动">
      <div class="timeline-row"><b>Thor</b><div class="slots"><span v-for="(_, i) in labels" :key="i" :class="i >= observation && i < arrival ? 'infer' : 'idle'">{{ i === observation ? '请求 B' : i > observation && i < arrival ? '推理' : '·' }}</span></div></div>
      <div class="timeline-row"><b>Orin</b><div class="slots"><span v-for="(slot, i) in labels" :key="i" :class="slot.kind">{{ slot.text }}</span></div></div>
    </div>
    <p class="demo-explanation" aria-live="polite">{{ explanation }}</p>
    <div class="legend"><span class="old">旧块 A</span><span class="new">新块 B</span><span class="blend">融合权重</span><span class="hold">H = hold</span></div>
    <p class="caption">机制示例：H=12、R=4、B=3，仅展示一次重规划；省略所有模式共同的首块等待。Sync 等待槽只表示墙钟时间，Async / Blend 槽表示实际控制步；槽宽不代表实测耗时。</p>
    <noscript>交互演示需要 JavaScript。下文提供完整的三模式机制与对齐说明。</noscript>
  </div>
</template>
