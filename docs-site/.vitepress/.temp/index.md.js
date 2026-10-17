import { resolveComponent, useSSRContext } from "vue";
import { ssrRenderAttrs, ssrRenderComponent } from "vue/server-renderer";
import { _ as _export_sfc } from "./plugin-vue_export-helper.1tPrXgE0.js";
const __pageData = JSON.parse('{"title":"项目概览","description":"","frontmatter":{"title":"项目概览"},"headers":[],"relativePath":"index.md","filePath":"index.md"}');
const _sfc_main = { name: "index.md" };
function _sfc_ssrRender(_ctx, _push, _parent, _attrs, $props, $setup, $data, $options) {
  const _component_SystemOverview = resolveComponent("SystemOverview");
  const _component_DeploymentGallery = resolveComponent("DeploymentGallery");
  const _component_TimelineDemo = resolveComponent("TimelineDemo");
  _push(`<div${ssrRenderAttrs(_attrs)}><h1 id="双设备推理-完整闭环" tabindex="-1">双设备推理，完整闭环 <a class="header-anchor" href="#双设备推理-完整闭环" aria-label="Permalink to &quot;双设备推理，完整闭环&quot;">​</a></h1><p class="lead">TurboVLA-SplitInfer 将观测预处理与动作执行留在 Orin Nano 8GB，将完整神经网络放在 Thor 128GB，通过同步、异步替换与异步融合比较控制效果。</p><p><a class="primary-link" href="./guide/deployment.html">开始部署</a><a href="./guide/completeness.html">查看代码与验证链路</a></p>`);
  _push(ssrRenderComponent(_component_SystemOverview, null, null, _parent));
  _push(`<h2 id="实物部署" tabindex="-1">实物部署 <a class="header-anchor" href="#实物部署" aria-label="Permalink to &quot;实物部署&quot;">​</a></h2><p>项目已在 <strong>Jetson Orin Nano 8GB 与 Jetson Thor 128GB</strong> 两台实体设备上部署。下图为项目现场设备的实拍整理版，分别对应观测与控制端、完整模型推理端。</p>`);
  _push(ssrRenderComponent(_component_DeploymentGallery, null, null, _parent));
  _push(`<p>部署步骤见<a href="./guide/deployment.html">设备部署</a>，三种模式的运行结果按<a href="./guide/validation.html">验证与结果</a>记录。</p><h2 id="先理解拆分边界" tabindex="-1">先理解拆分边界 <a class="header-anchor" href="#先理解拆分边界" aria-label="Permalink to &quot;先理解拆分边界&quot;">​</a></h2><p>跨设备传输的是<strong>归一化图像、8 维状态和语言指令</strong>。DINOv3、BERT、视觉语言交互、状态投影和 ACT 动作解码器全部在 Thor；Orin 不加载模型权重。返回值是可直接供 LIBERO 执行的 <strong>12 × 7 动作块</strong>。</p><p>本项目当前的双设备链路面向 <strong>LIBERO 相对动作控制</strong>。仓库保留 RoboTwin 训练与评测入口，但其三视角、50 步、14 维动作不适用于当前 split v1 协议。</p><h2 id="用同一套输入比较三种调度" tabindex="-1">用同一套输入比较三种调度 <a class="header-anchor" href="#用同一套输入比较三种调度" aria-label="Permalink to &quot;用同一套输入比较三种调度&quot;">​</a></h2>`);
  _push(ssrRenderComponent(_component_TimelineDemo, null, null, _parent));
  _push(`<table tabindex="0"><thead><tr><th>模式</th><th>要解决的问题</th><th>核心行为</th></tr></thead><tbody><tr><td>Sync</td><td>建立易解释的阻塞基线</td><td>用完动作块，再获取下一块</td></tr><tr><td>Async / <code>replace</code></td><td>在动作执行期间进行推理</td><td>对齐新动作，替换未来时间线</td></tr><tr><td>Blend</td><td>减小新旧指令切换差异</td><td>对重叠区前六维渐变，夹爪离散切换</td></tr></tbody></table><p>三种模式采用相同配置评测，通过成功率、控制间隔和往返延迟比较调度效果。</p><h2 id="最短验证路径" tabindex="-1">最短验证路径 <a class="header-anchor" href="#最短验证路径" aria-label="Permalink to &quot;最短验证路径&quot;">​</a></h2><ol><li>按<a href="./guide/deployment.html">设备部署</a>准备依赖、模型与 LIBERO assets。</li><li>Thor 启动模型服务，Orin 执行 <code>--preflight</code> 检查。</li><li>用单任务跑通三种模式，再扩大到多任务、多次试验。</li><li>按<a href="./guide/validation.html">验证与结果</a>核对成功率、控制间隔 p95、hold 与完整原始记录。</li></ol><h2 id="文档说明什么" tabindex="-1">文档说明什么 <a class="header-anchor" href="#文档说明什么" aria-label="Permalink to &quot;文档说明什么&quot;">​</a></h2><table tabindex="0"><thead><tr><th>需要了解</th><th>对应页面</th></tr></thead><tbody><tr><td>两台设备分别运行什么、传输什么</td><td><a href="./guide/architecture.html">双设备架构</a></td></tr><tr><td>动作如何对齐、何时融合、延迟时如何处理</td><td><a href="./guide/scheduling.html">调度机制</a></td></tr><tr><td>代码、入口、配置与测试是否形成闭环</td><td><a href="./guide/completeness.html">代码完整性</a></td></tr><tr><td>功能性、实时性、稳定性、安全性的实现与验证</td><td><a href="./guide/capabilities.html">系统能力</a></td></tr></tbody></table><p>本站提供代码入口、部署步骤、调度机制和结果分析方法。</p></div>`);
}
const _sfc_setup = _sfc_main.setup;
_sfc_main.setup = (props, ctx) => {
  const ssrContext = useSSRContext();
  (ssrContext.modules || (ssrContext.modules = /* @__PURE__ */ new Set())).add("index.md");
  return _sfc_setup ? _sfc_setup(props, ctx) : void 0;
};
const index = /* @__PURE__ */ _export_sfc(_sfc_main, [["ssrRender", _sfc_ssrRender]]);
export {
  __pageData,
  index as default
};
