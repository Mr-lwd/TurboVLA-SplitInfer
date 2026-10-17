import { ssrRenderAttrs } from "vue/server-renderer";
import { useSSRContext } from "vue";
import { _ as _export_sfc } from "./plugin-vue_export-helper.1tPrXgE0.js";
const __pageData = JSON.parse('{"title":"系统能力","description":"","frontmatter":{},"headers":[],"relativePath":"guide/capabilities.md","filePath":"guide/capabilities.md"}');
const _sfc_main = { name: "guide/capabilities.md" };
function _sfc_ssrRender(_ctx, _push, _parent, _attrs, $props, $setup, $data, $options) {
  _push(`<div${ssrRenderAttrs(_attrs)}><h1 id="系统能力" tabindex="-1">系统能力 <a class="header-anchor" href="#系统能力" aria-label="Permalink to &quot;系统能力&quot;">​</a></h1><p>从功能、性能和工程质量三个方面整理系统实现，并给出对应验证方式。</p><table tabindex="0"><thead><tr><th>维度</th><th>实现机制</th><th>验证方式 / 关键指标</th></tr></thead><tbody><tr><td>功能性</td><td>本机基线、远程 sync / replace / blend、LIBERO 12×7 动作闭环</td><td>成功率、三模式原始记录、数值一致性</td></tr><tr><td>实时性</td><td>单请求后台推理、keep-alive、快速无损压缩、控制节拍</td><td>控制间隔 p95、往返、hold、过期块</td></tr><tr><td>实用性</td><td>双端职责明确、统一入口、YAML、preflight</td><td>按部署步骤完成预检与单任务运行</td></tr><tr><td>稳定性</td><td>观测快照、动作对齐、过期裁剪、hold、异常传播</td><td>延迟注入、掉线、长时运行、hold 比例</td></tr><tr><td>安全性</td><td>报文限长、有界解压、形状/有限值校验、请求/实例匹配</td><td>非法载荷、服务重启、错误请求测试</td></tr><tr><td>一致性</td><td>无损压缩、严格权重加载、模型哈希、精度/块长检查</td><td>codec 位保真、同一 checkpoint 的 parity 对比</td></tr><tr><td>可复现性</td><td>seed、相同初始状态、模式顺序随机化、配置与环境元数据</td><td>原始记录、checkpoint SHA-256、设备环境</td></tr><tr><td>可观测性</td><td>调用/控制步 CSV、阶段计时、普通及墙钟视频</td><td>metadata、summary、comparison</td></tr><tr><td>可维护性</td><td>模型/协议/调度分层、六个测试模块、文档网站</td><td>单元回归、命令与链接核验</td></tr><tr><td>可扩展性</td><td>共用模型、独立 RoboTwin 训练评测入口、可选 codec</td><td>新适配与独立测试</td></tr></tbody></table><h2 id="运行条件" tabindex="-1">运行条件 <a class="header-anchor" href="#运行条件" aria-label="Permalink to &quot;运行条件&quot;">​</a></h2><p>split v1 使用 LIBERO 相对动作控制；控制频率配置为 20 Hz 上限，按实际时间戳统计运行节拍。请求超时或异常会结束当前实验并记录状态。依赖与模型资源见<a href="./deployment.html">设备部署</a>，内存与计时口径见<a href="./validation.html">验证与结果</a>。</p><p>当前客户端只支持 HTTP。服务适合受控实验网络，不应直接暴露到公网。若未来跨网络部署，应先增加 TLS、身份校验和访问控制，或使用明确配置的受保护隧道；现有 CLI 不能仅把 URL 改成 <code>https://</code> 就获得支持。</p><p><code>request_id</code> 和 <code>server_id</code> 用于一致性匹配，不是鉴权。无损张量协议避免 pickle 网络反序列化，但模型文件仍应来自可信来源。</p><p>真机部署还需要独立于推理线程的失联看门狗、速度/工作空间限制、碰撞防护与急停；零增量 hold 不能替代这些措施。</p><h2 id="验证顺序" tabindex="-1">验证顺序 <a class="header-anchor" href="#验证顺序" aria-label="Permalink to &quot;验证顺序&quot;">​</a></h2><p>按任务成功与动作一致性、延迟与缓冲状态、长时运行与资源监控的顺序验证。各阶段保存配置、设备环境和原始结果，便于复现与比较。</p></div>`);
}
const _sfc_setup = _sfc_main.setup;
_sfc_main.setup = (props, ctx) => {
  const ssrContext = useSSRContext();
  (ssrContext.modules || (ssrContext.modules = /* @__PURE__ */ new Set())).add("guide/capabilities.md");
  return _sfc_setup ? _sfc_setup(props, ctx) : void 0;
};
const capabilities = /* @__PURE__ */ _export_sfc(_sfc_main, [["ssrRender", _sfc_ssrRender]]);
export {
  __pageData,
  capabilities as default
};
