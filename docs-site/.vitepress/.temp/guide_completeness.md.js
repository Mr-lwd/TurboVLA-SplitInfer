import { ssrRenderAttrs } from "vue/server-renderer";
import { useSSRContext } from "vue";
import { _ as _export_sfc } from "./plugin-vue_export-helper.1tPrXgE0.js";
const __pageData = JSON.parse('{"title":"代码完整性","description":"","frontmatter":{},"headers":[],"relativePath":"guide/completeness.md","filePath":"guide/completeness.md"}');
const _sfc_main = { name: "guide/completeness.md" };
function _sfc_ssrRender(_ctx, _push, _parent, _attrs, $props, $setup, $data, $options) {
  _push(`<div${ssrRenderAttrs(_attrs)}><h1 id="代码完整性" tabindex="-1">代码完整性 <a class="header-anchor" href="#代码完整性" aria-label="Permalink to &quot;代码完整性&quot;">​</a></h1><p>项目覆盖“配置 → 服务 → 客户端 → 调度 → 执行 → 报告 → 测试”的完整实验链路，各模块提供对应入口、配置与验证方法。</p><h2 id="代码地图" tabindex="-1">代码地图 <a class="header-anchor" href="#代码地图" aria-label="Permalink to &quot;代码地图&quot;">​</a></h2><div class="language-text vp-adaptive-theme"><button title="Copy Code" class="copy"></button><span class="lang">text</span><pre class="shiki shiki-themes github-light github-dark vp-code" tabindex="0"><code><span class="line"><span>turbovla/</span></span>
<span class="line"><span>  models/       共用 TurboVLA：DINOv3、BERT、双向交互、ACT</span></span>
<span class="line"><span>  split/        Orin 客户端、Thor HTTP 服务、版本化张量协议</span></span>
<span class="line"><span>  evaluation/   策略适配、动作反归一化、三模式调度</span></span>
<span class="line"><span>  data/         LIBERO RLDS、混合套件、统计归一化</span></span>
<span class="line"><span>  training/     训练入口、优化器与 EMA</span></span>
<span class="line"><span>scripts/libero/ 基准入口、预检、通信测量、数值一致性、汇总</span></span>
<span class="line"><span>experiments/    LIBERO / RoboTwin 入口与配置</span></span>
<span class="line"><span>tests/          六个测试模块</span></span>
<span class="line"><span>third_party/    兼容运行时及保留许可证</span></span>
<span class="line"><span>docs-site/      本站源码与静态构建配置</span></span>
<span class="line"><span>assets/         原始架构图与图稿</span></span></code></pre></div><h2 id="从入口追到证据" tabindex="-1">从入口追到证据 <a class="header-anchor" href="#从入口追到证据" aria-label="Permalink to &quot;从入口追到证据&quot;">​</a></h2><table tabindex="0"><thead><tr><th>能力</th><th>入口 / 实现</th><th>配置或资源</th><th>验证证据</th></tr></thead><tbody><tr><td>Thor 推理服务</td><td><code>serve_thor.sh</code> → <code>split/server.py</code></td><td>checkpoint、DINOv3、BERT、stats</td><td><code>/health</code>、服务日志、split 测试</td></tr><tr><td>Orin 远程调用</td><td><code>split/client.py</code></td><td>URL、精度、codec</td><td>HTTP fake-policy 往返测试</td></tr><tr><td>传输编码</td><td><code>split/protocol.py</code></td><td>固定形状与协议版本</td><td>位保真、截断、附加数据、非有限值测试</td></tr><tr><td>三模式实验</td><td><code>benchmark_async.py</code> → <code>async_rollout.py</code></td><td><code>async_benchmark.yaml</code></td><td>对齐 / 融合 / 失败传播测试及 comparison</td></tr><tr><td>本机对照</td><td><code>benchmark_local.py</code></td><td><code>local_benchmark.yaml</code></td><td>本机入口与统计测试</td></tr><tr><td>模型输出一致性</td><td><code>check_split_parity.py</code></td><td>同一 checkpoint 与 stats</td><td>在 Thor 比较两条推理路径，生成 parity JSON</td></tr><tr><td>通信选型</td><td><code>benchmark_transport.py</code></td><td>固定观测 NPZ</td><td>相同动作约束下比较各 codec</td></tr><tr><td>训练与数据</td><td><code>training/</code>、<code>data/</code></td><td>RLDS/TFDS、统计、初始化资源</td><td>数据处理、训练配方与训练入口</td></tr><tr><td>RoboTwin 扩展</td><td><code>experiments/robotwin/</code></td><td>独立 all50 配置与外部 RoboTwin</td><td>独立训练与评测流程</td></tr></tbody></table><h2 id="外部资源清单" tabindex="-1">外部资源清单 <a class="header-anchor" href="#外部资源清单" aria-label="Permalink to &quot;外部资源清单&quot;">​</a></h2><table tabindex="0"><thead><tr><th>仓库内提供</th><th>需要另行准备</th></tr></thead><tbody><tr><td>模型实现、适配、服务、客户端、调度</td><td>模型权重及本地模型目录</td></tr><tr><td>YAML/JSON 配置、LIBERO 统计</td><td>LIBERO 代码、BDDL、初始状态和 assets</td></tr><tr><td>单元测试与报告脚本</td><td>JetPack、GPU 驱动、对应 PyTorch</td></tr><tr><td>数据处理与训练入口</td><td>训练数据和训练硬件</td></tr><tr><td>第三方许可说明</td><td>外部资源的获取及访问资格</td></tr></tbody></table><p>权重、数据、输出、视频与机器专用 <code>*.local.yaml</code> 按本地路径管理。发布项目时保留 <code>LICENSE</code> 和 <code>third_party/licenses/</code>，注明上游代码来源。</p><h2 id="阅读顺序" tabindex="-1">阅读顺序 <a class="header-anchor" href="#阅读顺序" aria-label="Permalink to &quot;阅读顺序&quot;">​</a></h2><ol><li><code>README.md</code>：安装、入口与约束。</li><li><code>async_benchmark.yaml</code>：实验参数。</li><li><code>split/client.py</code> → <code>protocol.py</code> → <code>server.py</code>：跨设备数据链路。</li><li><code>models/turbovla.py</code> → <code>action_head.py</code>：模型结构。</li><li><code>async_rollout.py::ActionTimeline.merge()</code>、<code>run_episode()</code>：时序行为。</li><li><code>benchmark_async.py::summarize_episodes()</code>：指标口径。</li></ol><h2 id="工程验证流程" tabindex="-1">工程验证流程 <a class="header-anchor" href="#工程验证流程" aria-label="Permalink to &quot;工程验证流程&quot;">​</a></h2><p>按“环境预检 → 模型输出一致性 → 三模式任务对比 → 长时运行”组织验证，保存配置、设备环境与结果文件。具体命令和指标见<a href="./validation.html">验证与结果</a>，网络及设备运行条件见<a href="./capabilities.html">系统能力</a>。</p></div>`);
}
const _sfc_setup = _sfc_main.setup;
_sfc_main.setup = (props, ctx) => {
  const ssrContext = useSSRContext();
  (ssrContext.modules || (ssrContext.modules = /* @__PURE__ */ new Set())).add("guide/completeness.md");
  return _sfc_setup ? _sfc_setup(props, ctx) : void 0;
};
const completeness = /* @__PURE__ */ _export_sfc(_sfc_main, [["ssrRender", _sfc_ssrRender]]);
export {
  __pageData,
  completeness as default
};
