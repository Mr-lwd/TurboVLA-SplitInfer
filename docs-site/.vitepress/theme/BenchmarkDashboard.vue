<script setup>
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import catalog from '../../../reports/evaluation/catalog.json'

const groupId = ref(catalog.featured_group)
const selected = ref('')
const group = computed(() => catalog.groups.find(g => g.id === groupId.value))
const rows = computed(() => group.value.run_ids.flatMap(id => {
  const run = catalog.runs.find(r => r.id === id)
  return run.records.map(record => ({ ...record, run, key: `${run.id}/${record.mode}` }))
}))
const active = computed(() => rows.value.find(row => row.key === selected.value) || rows.value[0])
const format = (value, digits = 2) => value == null ? '未记录' : Number(value).toFixed(digits)
const show = (row, key, stat = null) => stat ? row.metrics[key]?.[stat] : row.metrics[key]
</script>

<template>
  <section class="benchmark-panel" aria-label="实测数据浏览">
    <label for="benchmark-group">实验分组</label>
    <select id="benchmark-group" v-model="groupId" @change="selected = ''">
      <option v-for="item in catalog.groups" :key="item.id" :value="item.id">{{ item.title }}</option>
    </select>
    <p class="benchmark-hint">各项为独立运行的观测值；Async = replace。未记录的数据不补零，完整口径见下方静态表。</p>
    <div class="benchmark-scroll" tabindex="0" aria-label="结果对比表，可横向滚动">
      <table>
        <thead><tr><th>模式</th><th>成功</th><th>任务总耗时 / s</th><th>平均推理响应时间¹ / ms</th><th>控制间隔 p95 / ms</th><th>hold 步</th></tr></thead>
        <tbody><tr v-for="row in rows" :key="row.key">
          <th>{{ row.label }}</th><td>{{ row.metrics.successes }}/{{ row.metrics.episodes }}</td>
          <td>{{ format(show(row, 'rollout_wall_time_s')) }}</td>
          <td>{{ format(show(row, 'filtered_calls', 'mean_ms')) }}</td>
          <td>{{ format(show(row, 'control_intervals', 'p95_ms')) }}</td>
          <td>{{ format(show(row, 'hold_steps'), 0) }}</td>
        </tr></tbody>
      </table>
    </div>
    <p class="benchmark-hint">¹ 每 episode 排除前 N 次调用，N 在该运行详情中显示；推理响应时间按整块动作统计，远程模式包含预处理、传输和服务端推理。</p>
    <img :src="withBase(`/benchmarks/${group.id}.svg`)" :alt="`${group.title} 成功率、用时、调用延迟与控制间隔对比`" loading="lazy">
    <label for="benchmark-record">查看运行与逐任务明细</label>
    <select id="benchmark-record" :value="active.key" @change="selected = $event.target.value">
      <option v-for="row in rows" :key="row.key" :value="row.key">{{ row.label }} · {{ row.run.id }}</option>
    </select>
    <dl class="benchmark-facts">
      <div><dt>配置</dt><dd>{{ active.run.config.task_suite_name }} · {{ active.run.config.precision }} · seed {{ active.run.config.seed }} · chunk {{ active.run.config.chunk_size }}</dd></div>
      <div><dt>调用总数 / 过滤后</dt><dd>{{ active.metrics.all_calls.count }} / {{ active.metrics.filtered_calls.count }}；每回合排除 {{ active.run.exclude_first_calls }} 次</dd></div>
      <div><dt>首次推理平均响应时间</dt><dd>{{ format(active.metrics.first_call_per_episode.mean_ms) }} ms</dd></div>
      <div><dt>原始板卡记录</dt><dd>{{ active.run.hardware.board || '未记录' }}</dd></div>
      <div><dt>设备 / 功耗模式</dt><dd>{{ active.run.hardware.gpu_name }} / {{ active.run.hardware.nvpmodel || '未记录' }}</dd></div>
      <div><dt>PyTorch / CUDA</dt><dd>{{ active.run.hardware.torch }} / {{ active.run.hardware.cuda }}</dd></div>
      <div><dt>源代码版本</dt><dd>{{ active.run.git_commit }}{{ active.run.git_dirty ? '（记录时有未提交修改）' : '' }}</dd></div>
      <div><dt>权重哈希（记录值）</dt><dd>{{ active.run.server.checkpoint_sha256 || '未记录；不能凭文件名确认权重一致' }}</dd></div>
    </dl>
    <div class="benchmark-scroll" tabindex="0" aria-label="逐任务结果，可横向滚动">
      <table>
        <thead><tr><th>task / episode</th><th>结果</th><th>步数</th><th>任务耗时 / s</th><th>hold 步</th></tr></thead>
        <tbody><tr v-for="episode in active.episodes" :key="`${episode.task_id}/${episode.episode}`">
          <td :title="episode.instruction">{{ episode.task_id }} / {{ episode.episode }}</td>
          <td>{{ episode.success ? '成功' : '失败' }}</td><td>{{ episode.steps }}</td>
          <td>{{ format(episode.wall_s) }}</td><td>{{ format(episode.hold_steps, 0) }}</td>
        </tr></tbody>
      </table>
    </div>
    <details><summary>来源与校验摘要</summary>
      <p><code>{{ active.run.source_directory }}</code>（原始文件保留在设备上）</p>
      <ul><li v-for="source in active.run.source_files" :key="source.file"><code>{{ source.file }}</code><br>SHA-256: <code>{{ source.sha256 }}</code></li></ul>
    </details>
    <p><a :href="withBase('/benchmarks/catalog.json')" download>下载 JSON</a> · <a :href="withBase('/benchmarks/summary.csv')" download>下载 CSV</a></p>
  </section>
</template>

<style scoped>
.benchmark-panel { padding: 22px; background: #f2f7fc; margin: 26px 0; }
.benchmark-panel label { display: block; font-weight: 650; margin: 16px 0 8px; }
.benchmark-panel select { appearance: auto; padding: 9px 12px; border: 1px solid #9ab5ca; background: white; width: 100%; font: inherit; }
.benchmark-hint { font-size: 13px; color: #4e6070; }
.benchmark-scroll { overflow-x: auto; }
.benchmark-scroll table { display: table; font-size: 13px; min-width: 580px; }
.benchmark-scroll th, .benchmark-scroll td { padding: 8px 10px; white-space: nowrap; }
.benchmark-facts { font-size: 13px; margin: 16px 0; }
.benchmark-facts div { display: grid; grid-template-columns: 150px 1fr; gap: 12px; padding: 7px 0; border-bottom: 1px solid #dce8f1; }
.benchmark-facts dt { font-weight: 600; }
.benchmark-facts dd, .benchmark-panel code { overflow-wrap: anywhere; }
.benchmark-panel summary { cursor: pointer; font-weight: 600; }
.benchmark-panel select:focus-visible, .benchmark-scroll:focus-visible { outline: 3px solid #658eb5; outline-offset: 3px; }
@media (max-width: 600px) { .benchmark-panel { padding: 12px; } .benchmark-facts div { grid-template-columns: 1fr; gap: 3px; } }
</style>
