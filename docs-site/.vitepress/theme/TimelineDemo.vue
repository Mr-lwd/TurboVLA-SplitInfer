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
    if (i < arrival.value) return { kind: 'wait', text: 'Wait' }
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
  if (mode.value === 'sync') return `Request B after exhausting A. Control steps pause while waiting, then resume from B0.`
  if (delay.value >= 12) return `Chunk B, sampled at control step 4, is entirely stale and is discarded. This example does not show the next request.`
  const overlap = Math.min(3, Math.max(0, 12 - arrival.value), 12 - delay.value)
  return `Sample at step 4 and merge at step ${arrival.value}; discard the first ${delay.value} actions of B. ${mode.value === 'blend' && overlap ? `The remaining overlap is ${overlap} steps. Blend six pose dimensions; switch the gripper discretely.` : 'New actions replace the future timeline.'}`
})
</script>

<template>
  <div class="timeline-demo" data-ui>
    <div class="mode-buttons" role="group" aria-label="Choose scheduling mode">
      <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="mode = item.id">{{ item.name }}</button>
    </div>
    <label for="delay">{{ mode === 'sync' ? 'Illustrative waiting slots' : 'Control steps executed during the request' }} <strong>{{ delay }}</strong></label>
    <input id="delay" v-model.number="delay" type="range" min="1" max="12" step="1" />
    <div class="timeline-scroll" tabindex="0" aria-label="Action timeline; scroll horizontally">
      <div class="timeline-row"><b>Thor</b><div class="slots"><span v-for="(_, i) in labels" :key="i" :class="i >= observation && i < arrival ? 'infer' : 'idle'">{{ i === observation ? 'Req B' : i > observation && i < arrival ? 'Infer' : '·' }}</span></div></div>
      <div class="timeline-row"><b>Orin</b><div class="slots"><span v-for="(slot, i) in labels" :key="i" :class="slot.kind">{{ slot.text }}</span></div></div>
    </div>
    <p class="demo-explanation" aria-live="polite">{{ explanation }}</p>
    <div class="legend"><span class="old">Old chunk A</span><span class="new">New chunk B</span><span class="blend">Blend weight</span><span class="hold">H = hold</span></div>
    <p class="caption">Mechanism example: H=12, R=4, B=3; one replanning event, omitting the initial wait shared by all modes. Sync waiting slots represent wall time; Async/Blend slots represent executed control steps. Slot width is not measured duration.</p>
    <noscript>Enable JavaScript for this interactive example. The text below explains all modes and alignment rules.</noscript>
  </div>
</template>
