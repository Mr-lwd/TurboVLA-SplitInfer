<script setup>
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import catalog from '../../../reports/evaluation/catalog.json'

const groupId = ref(catalog.featured_group)
const selected = ref('')
const metricId = ref('inference')
const group = computed(() => catalog.groups.find(g => g.id === groupId.value))
const matched = computed(() => group.value.selection?.kind === 'common_success')
const excluded = computed(() => group.value.selection?.excluded.map(e => `${e.task_id}/${e.episode}`).join('、') || '无')
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
const thor = computed(() => rows.value.find(row => row.mode === 'local' && row.run.hardware.device_name === 'thor'))
const hasStages = computed(() => rows.value.some(row => row.metrics.remote_stage_timings))
const format = (value, digits = 2) => value == null ? '未记录' : Number(value).toFixed(digits)
const name = row => ({ 'Orin local': 'Orin 本机', 'Thor local': 'Thor 本机', 'Async / replace': 'Async' }[row.label] || row.label)
const color = row => ({ orin: '#637C97', thor: '#247F78', sync: '#BB8A4F', replace: '#557CAF', blend: '#9175A0' }[row.mode === 'local' ? row.run.hardware.device_name : row.mode] || '#637C97')
const metrics = computed(() => [
  { id: 'inference', label: '推理响应', title: '平均推理响应', unit: 'ms / 动作块', value: row => row.metrics.filtered_calls.mean_ms },
  { id: 'control', label: '控制间隔', title: '控制间隔 p95', unit: 'ms', value: row => row.metrics.control_intervals?.p95_ms },
  { id: 'wall', label: '任务耗时', title: '任务总耗时', unit: 's', value: row => row.metrics.rollout_wall_time_s },
  matched.value
    ? { id: 'success', label: '执行步数', title: '执行步数', unit: '步', value: row => row.metrics.executed_steps }
    : { id: 'success', label: '任务成功', title: '原始任务成功', unit: '成功次数 / 总次数', value: row => 100 * row.metrics.successes / row.metrics.episodes },
])
const metric = computed(() => metrics.value.find(item => item.id === metricId.value))
const maximum = computed(() => metricId.value === 'success' && !matched.value ? 100 : Math.max(1, ...rows.value.map(row => metric.value.value(row) ?? 0)))
const valueLabel = row => metricId.value === 'success'
  ? (matched.value ? String(row.metrics.executed_steps) : originalSuccess(row)) : format(metric.value.value(row))
</script>

<template>
  <section class="benchmark-panel" aria-label="实测数据浏览">
    <label class="field-label" for="benchmark-group">实验分组</label>
    <select id="benchmark-group" v-model="groupId" @change="selected = ''">
      <option v-for="item in catalog.groups" :key="item.id" :value="item.id">{{ item.title }}</option>
    </select>
    <p v-if="matched" class="selection-note"><strong>共同成功 {{ group.selection.retained.length }} 个案例</strong><br>{{ rows.length }} 种模式统一排除 task/episode：{{ excluded }}。从现有记录重算，无需重新评测。</p>
    <p v-else class="selection-note">原始全案例记录，包含失败回合；时间比较请切换至共同成功分组。</p>

    <div v-if="thor" class="thor-summary">
      <div class="summary-heading"><strong>Thor 本机</strong><span>{{ matched ? `共同成功 ${thor.metrics.episodes} 个案例` : `${originalSuccess(thor)} 任务成功` }}</span></div>
      <dl class="headline-metrics">
        <div><dt>平均推理响应</dt><dd>{{ format(thor.metrics.filtered_calls.mean_ms) }} <span>ms</span></dd></div>
        <div><dt>控制间隔 p95</dt><dd>{{ format(thor.metrics.control_intervals?.p95_ms) }} <span>ms</span></dd></div>
        <div><dt>任务总耗时</dt><dd>{{ format(thor.metrics.rollout_wall_time_s) }} <span>s</span></dd></div>
      </dl>
    </div>

    <div class="metric-switch" role="group" aria-label="选择对比指标">
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
    <p class="chart-caption">推理响应按完整动作块统计；首次调用的筛选规则见下方统计口径。</p>

    <details class="benchmark-details">
      <summary>统计口径与本组说明</summary>
      <p>推理响应包含预处理、计算、传输与动作转换。平均值与 p95 按每个 episode 排除前 N 次调用后统计；原始调用仍完整保留，未执行额外暖机。</p>
      <p v-if="matched">所有时间、阶段耗时与动作指标均使用同一成功案例交集。总耗时包含首次推理等待；控制间隔不额外剔除回合内的慢间隔。筛选后的案例数不代表整体成功率。</p>
      <ul><li v-for="run in rows.filter((row, index, list) => list.findIndex(other => other.run.id === row.run.id) === index)" :key="run.run.id">{{ run.run.hardware.device_name }} · {{ run.run.kind === 'local' ? '本机' : '协同' }}：每回合排除 {{ run.run.exclude_first_calls }} 次调用。</li></ul>
      <ul v-if="group.notes?.length"><li v-for="note in group.notes" :key="note">{{ note }}</li></ul>
      <p>Async 对应 replace；未记录的指标显示为“未记录”。不同轨迹和执行步数的总耗时不作为纯模型加速比。</p>
    </details>

    <figure v-if="hasStages" class="stage-chart">
      <div class="benchmark-scroll" tabindex="0" aria-label="推理耗时构成，可横向滚动">
        <img :src="withBase(`/benchmarks/${group.id}-stages.svg`)" alt="本机完整推理调用与协同推理各阶段的耗时对照，右侧列出平均值和 p95" loading="lazy">
      </div>
      <figcaption>本机为完整调用；协同分段均值相加等于响应均值。HTTP / 传输含接收等待与系统开销。</figcaption>
      <p class="download-links"><a :href="withBase(`/benchmarks/${group.id}-stages.svg`)" download>SVG 原图</a><a :href="withBase(`/benchmarks/${group.id}-stages.png`)" download>PNG 图片</a></p>
    </figure>

    <details class="benchmark-details">
      <summary>完整指标与逐任务记录</summary>
      <div class="benchmark-scroll" tabindex="0" aria-label="完整结果表，可横向滚动">
        <table>
          <thead><tr><th>设备 / 模式</th><th>{{ matched ? '共同成功案例数' : '原始成功 / 总数' }}</th><th>总耗时 / s</th><th>推理均值 / ms</th><th>推理 p95 / ms</th><th>控制 p95 / ms</th><th>hold</th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.key">
            <th>{{ name(row) }}</th><td>{{ matched ? row.metrics.episodes : originalSuccess(row) }}</td>
            <td>{{ format(row.metrics.rollout_wall_time_s) }}</td><td>{{ format(row.metrics.filtered_calls.mean_ms) }}</td>
            <td>{{ format(row.metrics.filtered_calls.p95_ms) }}</td><td>{{ format(row.metrics.control_intervals?.p95_ms) }}</td><td>{{ format(row.metrics.hold_steps, 0) }}</td>
          </tr></tbody>
        </table>
      </div>
      <label class="field-label" for="benchmark-record">运行详情</label>
      <select id="benchmark-record" :value="active.key" @change="selected = $event.target.value">
        <option v-for="row in rows" :key="row.key" :value="row.key">{{ name(row) }} · {{ row.run.id }}</option>
      </select>
      <dl class="benchmark-facts">
        <div v-if="matched"><dt>原始完整运行成功 / 总数</dt><dd>{{ originalSuccess(active) }}（包含被排除案例）</dd></div>
        <div><dt>配置</dt><dd>{{ active.run.config.task_suite_name }} · {{ active.run.config.precision }} · seed {{ active.run.config.seed }} · chunk {{ active.run.config.chunk_size }}</dd></div>
        <div><dt>调用总数 / 过滤后</dt><dd>{{ active.metrics.all_calls.count }} / {{ active.metrics.filtered_calls.count }}</dd></div>
        <div><dt>全部调用均值</dt><dd>{{ format(active.metrics.all_calls.mean_ms) }} ms（包含首次调用）</dd></div>
        <div><dt>每回合首次调用均值</dt><dd>{{ format(active.metrics.first_call_per_episode.mean_ms) }} ms</dd></div>
        <div><dt>原始板卡记录</dt><dd>{{ active.run.hardware.board || '未记录' }}</dd></div>
        <div><dt>设备 / 功耗模式</dt><dd>{{ active.run.hardware.gpu_name }} / {{ active.run.hardware.nvpmodel || '未记录' }}</dd></div>
        <div><dt>PyTorch / CUDA</dt><dd>{{ active.run.hardware.torch }} / {{ active.run.hardware.cuda }}</dd></div>
        <div><dt>源代码版本</dt><dd>{{ active.run.git_commit }}{{ active.run.git_dirty ? '（记录时有未提交修改）' : '' }}</dd></div>
        <div><dt>权重 SHA-256</dt><dd>{{ active.run.server.checkpoint_sha256 || '未记录' }}</dd></div>
      </dl>
      <div class="benchmark-scroll" tabindex="0" aria-label="逐任务结果，可横向滚动">
        <table>
          <thead><tr><th>task / episode</th><th>结果</th><th>步数</th><th>耗时 / s</th><th>hold</th></tr></thead>
          <tbody><tr v-for="episode in active.episodes" :key="`${episode.task_id}/${episode.episode}`">
            <td :title="episode.instruction">{{ episode.task_id }} / {{ episode.episode }}</td><td>{{ episode.success ? '成功' : '失败' }}</td>
            <td>{{ episode.steps }}</td><td>{{ format(episode.wall_s) }}</td><td>{{ format(episode.hold_steps, 0) }}</td>
          </tr></tbody>
        </table>
      </div>
      <details><summary>来源与校验摘要</summary>
        <p><code>{{ active.run.source_directory }}</code></p>
        <ul><li v-for="source in active.run.source_files" :key="source.file"><code>{{ source.file }}</code><br>SHA-256: <code>{{ source.sha256 }}</code></li></ul>
      </details>
    </details>
    <p class="download-links"><a :href="withBase('/benchmarks/catalog.json')" download>下载 JSON</a><a :href="withBase('/benchmarks/summary.csv')" download>下载 CSV</a></p>
  </section>
</template>

<style scoped>
.benchmark-panel { --ink: #243746; --muted: #617381; margin: 28px 0; color: var(--ink); min-width: 0; }
.selection-note { padding: 16px 20px; border-left: 3px solid #247F78; background: #f5f8fa; font-size: 16px; line-height: 1.8; }
.field-label { display: block; font-weight: 600; margin: 20px 0 10px; }
.benchmark-panel select { appearance: auto; padding: 12px 14px; border: 1px solid #d4dee4; border-radius: 8px; background: #fff; width: 100%; font: inherit; text-overflow: ellipsis; }
.thor-summary { margin: 26px 0 30px; padding: 24px; background: #f0f7f5; border-radius: 12px; }
.summary-heading { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.summary-heading strong { color: #216b65; font-size: 20px; }
.summary-heading span { color: var(--muted); font-size: 15px; }
.headline-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin: 22px 0 0; }
.headline-metrics dt { font-size: 15px; color: var(--muted); }
.headline-metrics dd { margin: 10px 0 0; font-size: clamp(24px, 2.4vw, 34px); line-height: 1.2; font-weight: 650; letter-spacing: -1px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.headline-metrics dd span { font-size: 16px; font-weight: 400; letter-spacing: 0; color: var(--muted); }
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
  .thor-summary { padding: 20px 16px; }
  .headline-metrics { grid-template-columns: 1fr; gap: 18px; }
  .headline-metrics div { display: flex; justify-content: space-between; align-items: baseline; }
  .headline-metrics dd { margin: 0; font-size: 30px; }
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
