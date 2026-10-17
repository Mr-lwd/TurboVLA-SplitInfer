# 实测数据维护

`catalog.json` 是可提交的精简数据源；`summary.csv`、根 README 中的结果区、文档数据页和
`assets/benchmarks/` 图表由脚本生成。原始动作、视频和设备路径记录保存在可提交的 `outputs/`。
每个导入项保留运行 ID、配置、软件/板卡信息、Git 版本、各模式汇总、逐 episode 数据，以及
实际读取的 metadata / 原始 JSON / summary 的 SHA-256。来源哈希用于追溯，不代表硬件认证。

## 默认对照：共同成功案例

默认图表只统计 Orin 本机、Thor 本机、Sync、Async / replace、Blend **全部成功的同一组 9 个案例**。
按 `(task_id, episode)` 对齐，保留 task **0、1、2、3、5、6、7、8、9**（episode 均为 0）。
Thor 本机与 Sync 的 task 4 失败，因此 **五种模式都排除 task 4**，包括该任务成功的其他模式。
本次仅从现有逐调用、逐控制步记录重新汇总，**没有重新运行评测**，没有按耗时阈值额外剔除慢样本。

| 模式 | 共同成功案例 | 总耗时 / s | 推理均值 / p95 / ms | 控制间隔 p95 / ms |
| --- | ---: | ---: | ---: | ---: |
| Orin 本机 | 9 | 71.40 | 125.01 / 127.70 | 192.13 |
| Thor 本机 | 9 | 26.95 | 31.15 / 33.36 | 55.83 |
| Sync | 9 | 74.76 | 134.03 / 285.30 | 167.40 |
| Async | 9 | 65.72 | 113.14 / 235.42 | 82.33 |
| Blend | 9 | 65.94 | 116.92 / 226.76 | 81.35 |

- 推理响应和各阶段均值 / p95：选出共同案例后，每回合排除首次调用，再合并剩余样本计算。
- 总耗时、控制间隔、步数、hold、阻塞、重叠比例等：均重新统计这 9 个案例；总耗时仍包含首次推理等待。
- 筛选后的 9 个案例不用于宣称整体成功率。原始成功数依次为 10/10、9/10、9/10、10/10、10/10。
- `catalog.groups[].selection` 保存保留 / 排除的任务键、失败来源和原始分组；`derived_records` 保存重算指标。
  原始 `runs[].records` 和 `outputs/` 不变。CSV 用 `selection=common_success` 标记筛选行，`all_episodes` 标记历史全案例行。
- 全案例分组作为历史记录保留（含失败），不参与默认时间对照。10 月 16 日旧 Orin 原始逐调用文件当前不在本机，
  该历史组保留已发布汇总，不推算其筛选后的分位数；这不影响默认组重算。

## 原始全案例记录（2026-10-17，含失败）

已加入 Orin 与 Thor 的独立本机运行，与现有三种协同模式并列展示。

| 本机设备 | 成功 | 总耗时 | 推理均值 / p95 | 控制间隔 p95 |
| --- | ---: | ---: | ---: | ---: |
| Orin | 10/10 | 81.91 s | 124.78 / 127.54 ms | 190.34 ms |
| Thor | 9/10 | 33.38 s | 31.05 / 33.22 ms | 56.34 ms |

- Orin：`orin_libero_spatial_bf16_20261017T180050_872432+0800`，1002 步、992 个控制间隔，过滤后 78 次推理。
- Thor：`thor_libero_spatial_bf16_20261017T180559_765357+0800`，1118 步、1108 个控制间隔，过滤后 87 次推理；task 4 失败，hold 为 0。
- Thor 全部 97 次调用的平均值为 **37.21 ms**，包含首次长耗时；该全案例组使用每回合排除首次调用后的 **31.05 ms**（默认共同成功组为 **31.15 ms**），没有额外暖机。

默认共同成功组的来源包含 **2026-10-17 的两台本机运行**与 **2026-10-16 的远程 Sync / Async / Blend**。
远程部分没有重新测量，历史分组保留。各运行的成功情况、轨迹和步数不同，总任务耗时不作为纯模型加速比。
本机没有墙钟限频，远程设置为 20 Hz 上限；控制间隔口径一致，执行节拍设置不同。

## 原始首批记录（2026-10-16，含失败）

- 本机：`orin_libero_spatial_bf16_20261016T211904_081157+0800`。
- 远程：`orin_to_thor_async_libero_spatial_20261016T224546_700348+0800`。
- 同为 LIBERO Spatial、10 个任务各 1 次、seed 7、BF16、chunk 12；远程每 4 步重规划、3 步融合、无额外人工延迟。
- 首批只收录 Orin 本机；Thor 的远程 `server_inference_s` 不等于 Thor 本机完整任务执行耗时。

本机成功 10/10，远程 Sync 为 9/10（task 4 失败），Async / Blend 均为 10/10。
本组包含失败回合，仅作原始记录追溯；时间对照以默认共同成功组为准。
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
  已收录的 Orin / Thor 本机 metadata 均未记录 checkpoint SHA-256，不能仅凭文件名证明与远程权重相同。
- 本组板卡 metadata 为 `NVIDIA Jetson Orin NX Engineering Reference Developer Kit`，
  与项目介绍中的 Orin Nano 标注存在差异。结果使用泛称 Orin，并保留原始 board 字符串供核对。
- 不跨运行自动池化，不将每任务 1 次的成功比例视为稳定成功率；比较时检查任务、初始状态、
  seed、权重、精度、版本、功耗和延迟设置。

## 后续追加

在仓库根目录、现有 TurboVLA Python 环境中运行。制图使用 Matplotlib（如缺少则安装
`python -m pip install matplotlib`），不需要 CUDA 推理或在线 Thor：

中文图表还需系统中文字体，例如 Ubuntu 的 `fonts-noto-cjk`（`sudo apt install fonts-noto-cjk`）。
图表同时生成 SVG 和 PNG，SVG 内嵌字形，浏览器及 GitHub 查看无需另装字体。
分阶段图只叠加相同样本集合的阶段均值；将往返拆为 Thor 解码/排队、推理与 HTTP/传输等开销，
另列剩余调用开销，使各段合计等于平均推理响应时间。本机只展示完整调用，不推测内部阶段。p95 独立展示，不相加。

```bash
# 导入一组完成的本机或远程运行；相同 ID 和相同内容重复导入不会重复计数
python scripts/libero/build_benchmark_report.py add /path/to/completed/run \
  --group libero-spatial-next --title 'LIBERO Spatial · 新一轮实验'
# 其他设备或模式加入同一组；不同设置宜使用新的 group
python scripts/libero/build_benchmark_report.py add /path/to/another/run \
  --group libero-spatial-next
# 从同组各模式原始记录重算共同成功案例（读取本地文件，不运行评测）
python scripts/libero/build_benchmark_report.py select-common-success \
  --source-group libero-spatial-next --group libero-spatial-next-common-success --featured
# 更新图、CSV、README 和文档数据页；此步骤仅需已提交的 catalog
python scripts/libero/build_benchmark_report.py build
```

本次默认组可重复生成：

```bash
python scripts/libero/build_benchmark_report.py select-common-success \
  --source-group libero-spatial-20261017 --group libero-spatial-common-success --featured
python scripts/libero/build_benchmark_report.py build
```

筛选命令要求各模式的任务集和 seed 一致，并校验现有原始文件及 SHA-256。
没有共同成功案例、原始文件缺失或数据变化时会报错，不会自动启动评测。
只有重新筛选需要原始文件；网页和图表重建直接使用 catalog 中的派生汇总。

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
精简 catalog、CSV、图表和生成文档足以重建网站，也可以提交 `outputs/` 内的原始评测数据、日志和视频；模型权重与缓存继续忽略。

## 分享完整原始输出

`outputs/` 已放行，当前评测文件可通过 `git add outputs/` 加入提交。若后续运行数量增多，也可以将某次运行目录
打包上传 GitHub Release，并附运行 ID；逐步 CSV、原始 JSON 和视频可一起归档。视频持续进入 Git 历史会增加
后续克隆体积，删除工作区文件也不会自动缩小已有历史。原始 metadata 和日志包含设备路径、主机名等环境信息，
发布前可检查内容；保留的源文件若被改写，需要重新计算相应来源哈希。
