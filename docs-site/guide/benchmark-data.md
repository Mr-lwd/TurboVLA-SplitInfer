# 实测数据维护

`catalog.json` 是可提交的精简数据源；`summary.csv`、根 README 中的结果区、文档数据页和
`assets/benchmarks/` 图表由脚本生成。原始动作、视频、绝对设备路径留在忽略提交的 `outputs/`。
每个导入项保留运行 ID、配置、软件/板卡信息、Git 版本、各模式汇总、逐 episode 数据，以及
实际读取的 metadata / 原始 JSON / summary 的 SHA-256。来源哈希用于追溯，不代表硬件认证。

## 首批数据（2026-10-16）

- 本机：`orin_libero_spatial_bf16_20261016T211904_081157+0800`。
- 远程：`orin_to_thor_async_libero_spatial_20261016T224546_700348+0800`。
- 同为 LIBERO Spatial、10 个任务各 1 次、seed 7、BF16、chunk 12；远程每 4 步重规划、3 步融合、无额外人工延迟。
- 首批只收录 Orin 本机；Thor 的远程 `server_inference_s` 不等于 Thor 本机完整任务执行耗时。

本机成功 10/10，远程 Sync 为 9/10（task 4 失败），Async / Blend 均为 10/10。
相对本组远程 Sync，Async / Blend 的任务总耗时分别降低 19.11% / 18.78%，
控制间隔 p95 分别降低 50.20% / 50.69%。总时间包括成功/失败轨迹差异，不是纯模型加速比。
Async 有 3 个 hold 步，Blend 为 0；Blend 的指令变化 L2 p95 为 0.198，Async 为 0.207，
单次小样本不足以证明成功率或动作平滑性的稳定优势。

## 统计口径

- 导入时用原始逐次调用重新计算均值、p95、任务/动作数等，并核对已保存汇总；不一致会报错。
- p95 按全部保留样本线性插值，不平均各 episode 的 p95。调用过滤按每个 episode 单独执行。
- 任务耗时指开始执行策略动作至回合结束的墙钟时间，排除模型加载、环境重置、初始稳定等待和视频编码；异步最后在途请求的 drain 单列。
- 本机旧数据没有逐控制步记录；控制间隔、hold、动作变化等保留 `null` / `—`，不补成 0。
- 更新后的本机入口会保存 `step_timings` 和 `_steps.csv`，自动计算 `control_intervals.p95_ms`。
  与异步版一样，先计算每回合内相邻 `action_start_s` 的差，再合并所有间隔求分位数；
  不跨回合、不排除首次推理后的控制步。首个动作之前的推理等待由首次推理指标体现。
  本机没有墙钟频率限制，远程入口默认限制为 20 Hz，因此时间戳口径相同也不代表执行节拍相同。
- 远程调用含 Orin 预处理、编码、网络和 Thor 推理；服务端分段耗时不是本机策略调用耗时。
- 本机与远程运行来自不同 Git 提交及运行时刻；Thor 的 PyTorch/CUDA 版本与 Orin 也不同。
  本机旧 metadata 未记录 checkpoint SHA-256，不能仅凭文件名证明与远程权重相同。
- 本组板卡 metadata 为 `NVIDIA Jetson Orin NX Engineering Reference Developer Kit`，
  与项目介绍中的 Orin Nano 标注存在差异。结果使用泛称 Orin，并保留原始 board 字符串供核对。
- 不跨运行自动池化，不将每任务 1 次的成功比例视为稳定成功率；比较时检查任务、初始状态、
  seed、权重、精度、版本、功耗和延迟设置。

## 后续追加

在仓库根目录、现有 TurboVLA Python 环境中运行。制图使用 Matplotlib（如缺少则安装
`python -m pip install matplotlib`），不需要 CUDA 推理或在线 Thor：

```bash
# 导入一组完成的本机或远程运行；相同 ID 和相同内容重复导入不会重复计数
python scripts/libero/build_benchmark_report.py add /path/to/completed/run \
  --group libero-spatial-next --title 'LIBERO Spatial · 新一轮实验'
# 其他设备或模式加入同一组；不同设置宜使用新的 group
python scripts/libero/build_benchmark_report.py add /path/to/another/run \
  --group libero-spatial-next
# 更新图、CSV、README 和文档数据页；此步骤仅需已提交的 catalog
python scripts/libero/build_benchmark_report.py build
```

新实验以独立 group 展示，历史数据保留。可编辑 catalog 的 `groups[].title` / `notes` 添加说明，
修改 `featured_group` 选择根 README 展示哪组；不要手工修改指标或生成区。
同一运行 ID 若源数据变化，导入会拒绝覆盖。失败/未完成的运行不能导入为完整对照。
脚本对分组内不同配置给出提示；即使配置相同，也不自动宣称严格受控实验。

```bash
cd docs-site
npm ci
npm run check
npm run build
```

网站支持按组切换和查看逐任务结果；资源清单从 catalog 自动发现图表，后续追加无需修改 Vue。
提交精简 catalog、CSV、图表和生成文档即可，原始权重、日志和视频仍不提交。
