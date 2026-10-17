<script setup>
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import catalog from '../../../reports/evaluation/latest.json'

const selected = ref('')
const metricId = ref('inference')
const group = computed(() => catalog.groups[0])
const matched = computed(() => group.value.selection?.kind === 'common_success')
const excluded = computed(() => group.value.selection?.excluded.map(e => `${e.task_id}/${e.episode}`).join(', ') || 'None')
const rows = computed(() => group.value.run_ids.flatMap(id => {
  const run = catalog.runs.find(r => r.id === id)
  const records = matched.value ? group.value.derived_records.filter(item => item.run_id === id).map(item => item.record) : run.records
  return records.map(record => ({ ...record, run, key: `${run.id}/${record.mode}` }))
}))
const originalSuccess = row => {
  const metrics = row.run.records.find(record => record.mode === row.mode).metrics
  return `${metrics.successes}/${metrics.episodes}`
}
const active = computed(() => rows.value.find(row => row.key === selected.value) || rows.value[0])
const hasStages = computed(() => rows.value.some(row => row.metrics.remote_stage_timings))
const format = (value, digits = 2) => value == null ? 'Not recorded' : Number(value).toFixed(digits)
const name = row => ({ 'Orin local': 'Orin local', 'Thor local': 'Thor local', 'Async / replace': 'Async' }[row.label] || row.label)
const color = row => ({ orin: '#637C97', thor: '#247F78', sync: '#BB8A4F', replace: '#557CAF', blend: '#9175A0' }[row.mode === 'local' ? row.run.hardware.device_name : row.mode] || '#637C97')
const metrics = computed(() => [
  { id: 'inference', label: 'Response latency', title: 'Mean response latency', unit: 'ms / chunk', value: row => row.metrics.filtered_calls.mean_ms },
  { id: 'control', label: 'Control interval', title: 'Control interval p95', unit: 'ms', value: row => row.metrics.control_intervals?.p95_ms },
  { id: 'wall', label: 'Task time', title: 'Total task time', unit: 's', value: row => row.metrics.rollout_wall_time_s },
  matched.value
    ? { id: 'success', label: 'Executed steps', title: 'Executed steps', unit: 'steps', value: row => row.metrics.executed_steps }
    : { id: 'success', label: 'Task success', title: 'Original task success', unit: 'Successes / episodes', value: row => 100 * row.metrics.successes / row.metrics.episodes },
])
const metric = computed(() => metrics.value.find(item => item.id === metricId.value))
const maximum = computed(() => metricId.value === 'success' && !matched.value ? 100 : Math.max(1, ...rows.value.map(row => metric.value.value(row) ?? 0)))
const valueLabel = row => metricId.value === 'success'
  ? (matched.value ? String(row.metrics.executed_steps) : originalSuccess(row)) : format(metric.value.value(row))
</script>

<template>
  <section class="benchmark-panel" aria-label="Benchmark explorer">
    <p v-if="matched" class="selection-note"><strong>{{ group.selection.retained.length }} commonly successful cases</strong><br>All {{ rows.length }} modes exclude task/episode {{ excluded }}. Recomputed from existing records.</p>
    <p v-else class="selection-note">Current complete runs, aggregated across all episodes.</p>

    <div class="metric-switch" role="group" aria-label="Choose comparison metric">
      <button v-for="item in metrics" :key="item.id" :aria-pressed="metricId === item.id" @click="metricId = item.id">{{ item.label }}</button>
    </div>
    <figure class="metric-chart" :aria-label="metric.title">
      <figcaption><strong>{{ metric.title }}</strong><span>{{ metric.unit }}</span></figcaption>
      <div class="chart-rows" aria-live="polite">
        <div v-for="row in rows" :key="row.key" class="chart-row" :style="{ '--mode-color': color(row) }">
          <span class="chart-name"><i aria-hidden="true"></i>{{ name(row) }}</span>
          <div class="bar-track" aria-hidden="true"><div class="bar-fill" :style="{ width: `${100 * (metric.value(row) ?? 0) / maximum}%` }"></div></div>
          <strong class="chart-value">{{ valueLabel(row) }}</strong>
        </div>
      </div>
    </figure>
    <p class="chart-caption">Response latency is measured per complete action chunk. See the methodology below for initial-call filtering.</p>

    <details class="benchmark-details">
      <summary>Methodology</summary>
      <p>Response latency includes preprocessing, computation, transport and action conversion. Mean and p95 exclude the first N calls in each episode; all raw calls are retained, with no additional evaluation warmup.</p>
      <p v-if="matched">Timing, stage and action metrics use the same intersection of successful cases. Total duration includes initial inference waits; slow within-episode control intervals are retained. The selected case count is not the overall success rate.</p>
      <ul><li v-for="run in rows.filter((row, index, list) => list.findIndex(other => other.run.id === row.run.id) === index)" :key="run.run.id">{{ run.run.hardware.device_name }} · {{ run.run.kind === 'local' ? 'Local' : 'Remote' }}: exclude {{ run.run.exclude_first_calls }} calls per episode.</li></ul>
      <ul v-if="group.notes?.length"><li v-for="note in group.notes" :key="note">{{ note }}</li></ul>
      <p>Async maps to replace. Missing metrics are shown as Not recorded. Duration differences across trajectories and action counts are not pure model speedups.</p>
    </details>

    <figure v-if="hasStages" class="stage-chart">
      <div class="benchmark-scroll" tabindex="0" aria-label="Latency breakdown; scroll horizontally">
        <img :src="withBase(`/benchmarks/${group.id}-stages.svg`)" alt="Complete local calls and remote latency stages, with mean and p95 on the right" loading="lazy">
      </div>
      <figcaption>Local bars show complete calls. Remote stage means sum to mean response latency. HTTP/transport includes receive waits and system overhead.</figcaption>
      <p class="download-links"><a :href="withBase(`/benchmarks/${group.id}-stages.svg`)" download>Download SVG</a><a :href="withBase(`/benchmarks/${group.id}-stages.png`)" download>Download PNG</a></p>
    </figure>

    <details class="benchmark-details">
      <summary>Full metrics and task records</summary>
      <div class="benchmark-scroll" tabindex="0" aria-label="Complete results; scroll horizontally">
        <table>
          <thead><tr><th>Device / mode</th><th>{{ matched ? 'Matched cases' : 'Original success / total' }}</th><th>Total time / s</th><th>Mean response / ms</th><th>Response p95 / ms</th><th>Control p95 / ms</th><th>hold</th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.key">
            <th>{{ name(row) }}</th><td>{{ matched ? row.metrics.episodes : originalSuccess(row) }}</td>
            <td>{{ format(row.metrics.rollout_wall_time_s) }}</td><td>{{ format(row.metrics.filtered_calls.mean_ms) }}</td>
            <td>{{ format(row.metrics.filtered_calls.p95_ms) }}</td><td>{{ format(row.metrics.control_intervals?.p95_ms) }}</td><td>{{ format(row.metrics.hold_steps, 0) }}</td>
          </tr></tbody>
        </table>
      </div>
      <label class="field-label" for="benchmark-record">Run details</label>
      <select id="benchmark-record" :value="active.key" @change="selected = $event.target.value">
        <option v-for="row in rows" :key="row.key" :value="row.key">{{ name(row) }}</option>
      </select>
      <dl class="benchmark-facts">
        <div v-if="matched"><dt>Full-run success / total</dt><dd>{{ originalSuccess(active) }} (including excluded cases)</dd></div>
        <div><dt>Configuration</dt><dd>{{ active.run.config.task_suite_name }} · {{ active.run.config.precision }} · seed {{ active.run.config.seed }} · chunk {{ active.run.config.chunk_size }}</dd></div>
        <div><dt>Calls: all / filtered</dt><dd>{{ active.metrics.all_calls.count }} / {{ active.metrics.filtered_calls.count }}</dd></div>
        <div><dt>Mean of all calls</dt><dd>{{ format(active.metrics.all_calls.mean_ms) }} ms (including initial calls)</dd></div>
        <div><dt>Mean first call per episode</dt><dd>{{ format(active.metrics.first_call_per_episode.mean_ms) }} ms</dd></div>
        <div><dt>Recorded board</dt><dd>{{ active.run.hardware.board || 'Not recorded' }}</dd></div>
        <div><dt>Device / power mode</dt><dd>{{ active.run.hardware.gpu_name }} / {{ active.run.hardware.nvpmodel || 'Not recorded' }}</dd></div>
        <div><dt>PyTorch / CUDA</dt><dd>{{ active.run.hardware.torch }} / {{ active.run.hardware.cuda }}</dd></div>
        <div><dt>Source revision</dt><dd>{{ active.run.git_commit }}{{ active.run.git_dirty ? ' (uncommitted changes at recording)' : '' }}</dd></div>
        <div><dt>Checkpoint SHA-256</dt><dd>{{ active.run.server.checkpoint_sha256 || 'Not recorded' }}</dd></div>
      </dl>
      <div class="benchmark-scroll" tabindex="0" aria-label="Per-task results; scroll horizontally">
        <table>
          <thead><tr><th>task / episode</th><th>Result</th><th>Steps</th><th>Time / s</th><th>hold</th></tr></thead>
          <tbody><tr v-for="episode in active.episodes" :key="`${episode.task_id}/${episode.episode}`">
            <td :title="episode.instruction">{{ episode.task_id }} / {{ episode.episode }}</td><td>{{ episode.success ? 'Success' : 'Failure' }}</td>
            <td>{{ episode.steps }}</td><td>{{ format(episode.wall_s) }}</td><td>{{ format(episode.hold_steps, 0) }}</td>
          </tr></tbody>
        </table>
      </div>
      <details><summary>Sources and checksums</summary>
        <p>Run IDs, original filenames and SHA-256 checksums are available in the JSON download.</p>
      </details>
    </details>
    <p class="download-links"><a :href="withBase('/benchmarks/latest.json')" download>Download JSON</a><a :href="withBase('/benchmarks/summary.csv')" download>Download CSV</a></p>
  </section>
</template>

<style scoped>
.benchmark-panel { --ink: #243746; --muted: #617381; margin: 28px 0; color: var(--ink); min-width: 0; }
.selection-note { padding: 16px 20px; border-left: 3px solid #247F78; background: #f5f8fa; font-size: 16px; line-height: 1.8; }
.field-label { display: block; font-weight: 600; margin: 20px 0 10px; }
.benchmark-panel select { appearance: auto; padding: 12px 14px; border: 1px solid #d4dee4; border-radius: 8px; background: #fff; width: 100%; font: inherit; text-overflow: ellipsis; }
.metric-switch { display: flex; gap: 5px; padding: 5px; background: #f2f5f7; border-radius: 10px; }
.metric-switch button { flex: 1; padding: 10px 8px; font-size: 15px; font-weight: 600; border-radius: 7px; white-space: nowrap; }
.metric-switch button[aria-pressed=true] { color: #216b65; background: #fff; box-shadow: 0 1px 4px #24374612; }
.metric-chart { margin: 26px 0 18px; }
.metric-chart figcaption { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 28px; }
.metric-chart figcaption strong { font-size: 23px; }
.metric-chart figcaption span { font-size: 15px; color: var(--muted); }
.chart-rows { display: grid; gap: 23px; }
.chart-row { display: grid; grid-template-columns: 118px minmax(0, 1fr) 90px; gap: 16px; align-items: center; }
.chart-name { font-size: 16px; white-space: nowrap; display: flex; gap: 9px; align-items: center; }
.chart-name i { width: 8px; height: 8px; border-radius: 50%; background: var(--mode-color); flex: none; }
.bar-track { height: 23px; border-radius: 4px; background: #f2f5f7; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; background: var(--mode-color); transition: width .2s ease; }
.chart-value { text-align: right; font-size: 23px; font-weight: 600; font-variant-numeric: tabular-nums; }
.chart-caption, .stage-chart figcaption { color: var(--muted); font-size: 15px; line-height: 1.75; }
.benchmark-details { margin: 22px 0; border-top: 1px solid #e3e9ed; padding-top: 17px; }
.benchmark-panel summary { cursor: pointer; font-size: 16px; font-weight: 600; }
.benchmark-details p, .benchmark-details li { font-size: 15px; }
.benchmark-scroll { overflow-x: auto; }
.benchmark-scroll table { display: table; font-size: 15px; min-width: 580px; }
.benchmark-scroll th, .benchmark-scroll td { padding: 10px 12px; white-space: nowrap; }
.benchmark-facts { font-size: 15px; margin: 20px 0; }
.benchmark-facts div { display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 12px; padding: 10px 0; border-bottom: 1px solid #e3e9ed; }
.benchmark-facts dt { font-weight: 600; }
.benchmark-facts dd { margin: 0; }
.benchmark-facts dd, .benchmark-panel code { overflow-wrap: anywhere; }
.stage-chart { margin: 32px 0; }
.stage-chart img { width: 100%; min-width: 760px; max-width: none; }
.download-links { display: flex; flex-wrap: wrap; gap: 20px; font-size: 15px; }
.benchmark-panel select:focus-visible, .benchmark-panel button:focus-visible, .benchmark-panel summary:focus-visible, .benchmark-scroll:focus-visible { outline: 3px solid #557caf; outline-offset: 3px; }
@media (max-width: 600px) {
  .metric-switch { flex-wrap: wrap; }
  .metric-switch button { flex-basis: calc(50% - 5px); }
  .chart-row { grid-template-columns: 1fr auto; gap: 10px; }
  .bar-track { grid-column: 1 / -1; grid-row: 2; height: 18px; }
  .chart-value { grid-column: 2; grid-row: 1; }
  .chart-rows { gap: 22px; }
  .benchmark-facts div { grid-template-columns: 1fr; gap: 4px; }
}
@media (prefers-reduced-motion: reduce) { .bar-fill { transition: none; } }
</style>
