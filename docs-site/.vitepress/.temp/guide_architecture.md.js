import { resolveComponent, useSSRContext } from "vue";
import { ssrRenderAttrs, ssrRenderAttr, ssrRenderComponent } from "vue/server-renderer";
import { _ as _export_sfc } from "./plugin-vue_export-helper.1tPrXgE0.js";
const _imports_0 = "/figures/framework-flat.png";
const _imports_1 = "/figures/architecture-overview.png";
const __pageData = JSON.parse('{"title":"双设备架构","description":"","frontmatter":{},"headers":[],"relativePath":"guide/architecture.md","filePath":"guide/architecture.md"}');
const _sfc_main = { name: "guide/architecture.md" };
function _sfc_ssrRender(_ctx, _push, _parent, _attrs, $props, $setup, $data, $options) {
  const _component_DiagramDownload = resolveComponent("DiagramDownload");
  _push(`<div${ssrRenderAttrs(_attrs)}><h1 id="双设备架构" tabindex="-1">双设备架构 <a class="header-anchor" href="#双设备架构" aria-label="Permalink to &quot;双设备架构&quot;">​</a></h1><p>将完整模型集中到 Thor，使 Orin Nano 的内存主要用于仿真、观测和控制链路。这里是<strong>系统职责拆分</strong>，神经网络层之间没有跨设备切分。</p><h2 id="拆分推理框架图" tabindex="-1">拆分推理框架图 <a class="header-anchor" href="#拆分推理框架图" aria-label="Permalink to &quot;拆分推理框架图&quot;">​</a></h2><p><img${ssrRenderAttr("src", _imports_0)} alt="Orin Nano 8GB 与 Thor 128GB 拆分推理框架，纯色模块及连续数据流"></p>`);
  _push(ssrRenderComponent(_component_DiagramDownload, null, null, _parent));
  _push(`<p>框架图由 DDS 生成后重建为原生文本、纯色形状及单个连续箭头；相机与机械臂为独立图标对象。图中 token 方块仅作结构示意，实际数量以配置为准。</p><h2 id="数据走向" tabindex="-1">数据走向 <a class="header-anchor" href="#数据走向" aria-label="Permalink to &quot;数据走向&quot;">​</a></h2><table tabindex="0"><thead><tr><th>环节</th><th>位置</th><th>输入 → 输出</th><th>代码</th></tr></thead><tbody><tr><td>观测快照</td><td>Orin</td><td>两路相机、位姿、夹爪状态 → 独立副本</td><td><code>async_rollout.py::submit()</code></td></tr><tr><td>预处理</td><td>Orin</td><td>256×256 RGB、8 维状态 → 归一化张量</td><td><code>split/client.py</code></td></tr><tr><td>编码</td><td>Orin</td><td>张量 + JSON 头 → 无损压缩报文</td><td><code>split/protocol.py</code></td></tr><tr><td>神经推理</td><td>Thor</td><td>DINOv3 + 在线 BERT → 双向 V–L 交互 → ACT</td><td><code>models/turbovla.py</code></td></tr><tr><td>状态融合</td><td>Thor</td><td>8 维状态 → state tokens → ACT memory</td><td><code>models/action_head.py</code></td></tr><tr><td>动作还原</td><td>Thor</td><td>归一化输出 → 相对位姿 + 离散夹爪</td><td><code>evaluation/suite_policy.py</code></td></tr><tr><td>对齐与执行</td><td>Orin</td><td>动作块 → 实际控制步时间线 → <code>env.step()</code></td><td><code>evaluation/async_rollout.py</code></td></tr></tbody></table><h2 id="模型继承关系" tabindex="-1">模型继承关系 <a class="header-anchor" href="#模型继承关系" aria-label="Permalink to &quot;模型继承关系&quot;">​</a></h2><p><img${ssrRenderAttr("src", _imports_1)} alt="上游 TurboVLA 模型结构：DINOv3、BERT、视觉语言交互和动作块解码"></p><p>原始结构图来自仓库 <code>assets/figures/architecture-overview.png</code>。双设备设计保留其模型语义：视觉与语言特征经过双向交互，生成 action-ready features；机器人状态通过独立投影后，与融合特征一起送入 ACT 解码器。</p><p>LIBERO 默认配置包含 6 层交互模块、3 层 ACT 解码器；实际运行以 checkpoint 的 <code>model_config</code> 为准。BERT 在线编码，不将“冻结参数”误写成“离线文本特征缓存”。</p><h2 id="传输契约" tabindex="-1">传输契约 <a class="header-anchor" href="#传输契约" aria-label="Permalink to &quot;传输契约&quot;">​</a></h2><table tabindex="0"><thead><tr><th>内容</th><th>split v1 约束</th></tr></thead><tbody><tr><td>图像张量</td><td><code>[1, 2, 3, 256, 256]</code>，RGB 预处理后传输</td></tr><tr><td>状态张量</td><td><code>[1, 8]</code></td></tr><tr><td>精度</td><td><code>bf16</code> / <code>fp32</code>，两端一致</td></tr><tr><td>动作</td><td>最多 12 步，每步 7 维，有限值</td></tr><tr><td>上行</td><td>4 字节头长度 + JSON 元信息 + 压缩张量</td></tr><tr><td>下行</td><td>JSON 动作、请求标识、服务标识、计时、可选显存指标</td></tr><tr><td>压缩</td><td>zlib、LZ4、Zstandard，可搭配字节 shuffle</td></tr><tr><td>连接</td><td>HTTP/1.1 keep-alive；不自动重放 POST</td></tr></tbody></table><p>无损指的是压缩保留<strong>已选精度张量</strong>的位模式。FP32 转 BF16 本身不是无损转换。</p><h2 id="两个执行线程" tabindex="-1">两个执行线程 <a class="header-anchor" href="#两个执行线程" aria-label="Permalink to &quot;两个执行线程&quot;">​</a></h2><p>Orin 主线程按控制步运行环境；后台 worker 执行预处理、压缩和远程请求，最多一个请求在途。Thor 用锁串行访问模型。异步模式重叠的是<strong>请求链路与控制执行</strong>，不是在 Thor 上同时运行多个推理请求。</p><h2 id="资源边界" tabindex="-1">资源边界 <a class="header-anchor" href="#资源边界" aria-label="Permalink to &quot;资源边界&quot;">​</a></h2><p>“8GB / 128GB”标注设备内存容量，不代表模型实测占用。PyTorch allocator peak 只覆盖框架分配器，不能代替 Jetson 总共享内存、仿真显存或系统峰值。应配合设备侧资源监控记录实机运行。</p></div>`);
}
const _sfc_setup = _sfc_main.setup;
_sfc_main.setup = (props, ctx) => {
  const ssrContext = useSSRContext();
  (ssrContext.modules || (ssrContext.modules = /* @__PURE__ */ new Set())).add("guide/architecture.md");
  return _sfc_setup ? _sfc_setup(props, ctx) : void 0;
};
const architecture = /* @__PURE__ */ _export_sfc(_sfc_main, [["ssrRender", _sfc_ssrRender]]);
export {
  __pageData,
  architecture as default
};
