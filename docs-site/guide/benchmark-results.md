# 实测数据

数据来自已完成的运行记录；下表与图由同一份可追加的数据目录生成。Async 对应 CLI 的 `replace`。

<BenchmarkDashboard />

## 静态对照与下载

¹ 推理响应时间的均值和 p95 均按每个 episode 排除前 N 次调用后汇总；N 见来源表。推理响应时间是从发起策略调用到收到整块动作的耗时；远程模式包含预处理、传输和服务端推理，不是每步耗时。`—` 表示原记录缺失。

[下载结构化数据](../../reports/evaluation/catalog.json) · [下载汇总 CSV](../../reports/evaluation/summary.csv)

<details class="benchmark-archive"><summary>LIBERO Spatial · 共同成功 9 个案例 · 静态图表与明细</summary>

## LIBERO Spatial · 共同成功 9 个案例

共同成功 9 个案例 · 排除 task/episode：4/0

| 设备 / 模式 | 共同成功案例数 | 执行步数 | 任务总耗时 / s | 平均推理响应时间¹ / ms | 推理响应时间 p95¹ / ms | 控制间隔 p95 / ms | hold 步 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 9 | 868 | 71.40 | 125.01 | 127.70 | 192.13 | 0 |
| Thor local | 9 | 898 | 26.95 | 31.15 | 33.36 | 55.83 | 0 |
| Sync | 9 | 902 | 74.76 | 134.03 | 285.30 | 167.40 | 0 |
| Async / replace | 9 | 900 | 65.72 | 113.14 | 235.42 | 82.33 | 3 |
| Blend | 9 | 893 | 65.94 | 116.92 | 226.76 | 81.35 | 0 |

![LIBERO Spatial · 共同成功 9 个案例 四项指标](../../assets/benchmarks/libero-spatial-common-success.svg)

- 仅统计全部 5 种模式共同成功的 9 个案例；统一排除：task 4 / episode 0。
- 使用现有原始记录重算，未重新评测。按 task ID / episode 匹配；均值与 p95 从保留调用和控制步重新汇总。
- 共同成功样本数不代表整体成功率；完整运行的失败记录和成功比例保留在原始全案例分组。
- 推理均值与 p95 仍按每回合排除首次调用；任务总耗时包含首次推理等待，控制间隔不额外剔除回合内的慢间隔。
- 原始组说明：Orin / Thor 本机为 2026-10-17 运行；远程 Sync / Async / Blend 沿用 2026-10-16 的记录。历史分组保留，不跨运行合并样本。
- 原始组说明：同为 LIBERO Spatial、10 个任务各 1 次、seed 7、BF16、chunk 12。本机无墙钟限频，远程为 20 Hz 上限；远程重规划间隔 4 步、融合窗口 3 步、额外延迟 0。
- 原始组说明：Orin 本机成功 10/10、1002 步；Thor 本机成功 9/10、1118 步，task 4 失败。远程 Sync 同样在 task 4 失败；各模式轨迹与执行步数不同，总耗时差不等于纯模型加速。
- 原始组说明：各次运行来自不同代码提交与运行时刻；本机 metadata 未记录 checkpoint SHA-256，不能仅凭文件名确认与远程权重一致。
- 原始组说明：Orin 板卡 metadata 为 Orin NX Engineering Reference Developer Kit，与项目 Orin Nano 标注存在差异，结果保留 Orin 泛称。

### 调度与调用明细

| 模式 | 调用总数 / 过滤后 | 首次推理平均响应时间 / ms | 首段后阻塞 / s | 推理与 env.step 重叠比例 | drain / s | 指令变化 L2 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 76 / 67 | 344.75 | — | — | — | — |
| Thor local | 78 / 69 | 96.32 | — | — | — | — |
| Sync | 78 / 69 | 169.40 | 9.295 | 0.00 | 0.005 | 0.199 |
| Async / replace | 224 / 215 | 117.50 | 0.000 | 94.14 | 0.012 | 0.211 |
| Blend | 226 / 217 | 135.29 | 0.000 | 93.74 | 0.076 | 0.199 |

重叠比例单位为 %；L2 是相邻六维相对指令差值，混合了平移/旋转单位，不是物理 jerk。

### 推理耗时构成

![本机完整调用与协同推理各阶段耗时](../../assets/benchmarks/libero-spatial-common-success-stages.svg)

[下载 SVG](../../assets/benchmarks/libero-spatial-common-success-stages.svg) · [下载 PNG](../../assets/benchmarks/libero-spatial-common-success-stages.png)

本机显示完整调用；协同模式按同一过滤样本分解，各阶段均值之和等于平均响应。p95 独立统计。完整口径见[数据维护说明](./benchmark-data.md)。

| 协同模式 | Orin 预处理 | 编码压缩 | Thor 解码/排队 | Thor 推理 | HTTP/传输 | 其他开销 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sync | 6.99 | 6.87 | 2.72 | 28.81 | 88.41 | 0.24 |
| Async / replace | 11.02 | 7.46 | 2.68 | 27.93 | 63.74 | 0.32 |
| Blend | 10.35 | 7.28 | 2.68 | 27.95 | 68.36 | 0.31 |

单位：ms。HTTP/传输包含接收等待与系统开销；阶段不足或样本不齐时不推测分解。

### 数据来源

| 来源运行 | 配置 | 每回合排除调用数 |
| --- | --- | ---: |
| `orin_to_thor_async_libero_spatial_20261016T224546_700348+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| `orin_libero_spatial_bf16_20261017T180050_872432+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| `thor_libero_spatial_bf16_20261017T180559_765357+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |

### 逐任务结果

| 模式 | task ID | episode | 成功 | 步数 | 任务耗时 / s | hold 步 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Orin local | 0 | 0 | 是 | 76 | 7.81 | 0 |
| Orin local | 1 | 0 | 是 | 111 | 8.52 | 0 |
| Orin local | 2 | 0 | 是 | 90 | 7.04 | 0 |
| Orin local | 3 | 0 | 是 | 80 | 6.18 | 0 |
| Orin local | 5 | 0 | 是 | 95 | 7.69 | 0 |
| Orin local | 6 | 0 | 是 | 100 | 8.24 | 0 |
| Orin local | 7 | 0 | 是 | 107 | 9.13 | 0 |
| Orin local | 8 | 0 | 是 | 96 | 7.47 | 0 |
| Orin local | 9 | 0 | 是 | 113 | 9.33 | 0 |
| Thor local | 0 | 0 | 是 | 79 | 2.62 | 0 |
| Thor local | 1 | 0 | 是 | 118 | 3.40 | 0 |
| Thor local | 2 | 0 | 是 | 95 | 2.54 | 0 |
| Thor local | 3 | 0 | 是 | 87 | 2.51 | 0 |
| Thor local | 5 | 0 | 是 | 93 | 2.85 | 0 |
| Thor local | 6 | 0 | 是 | 105 | 3.32 | 0 |
| Thor local | 7 | 0 | 是 | 113 | 3.50 | 0 |
| Thor local | 8 | 0 | 是 | 94 | 2.66 | 0 |
| Thor local | 9 | 0 | 是 | 114 | 3.56 | 0 |
| Sync | 0 | 0 | 是 | 80 | 6.30 | 0 |
| Sync | 1 | 0 | 是 | 114 | 8.90 | 0 |
| Sync | 2 | 0 | 是 | 96 | 7.78 | 0 |
| Sync | 3 | 0 | 是 | 86 | 7.53 | 0 |
| Sync | 5 | 0 | 是 | 96 | 7.77 | 0 |
| Sync | 6 | 0 | 是 | 108 | 9.15 | 0 |
| Sync | 7 | 0 | 是 | 112 | 9.74 | 0 |
| Sync | 8 | 0 | 是 | 94 | 7.22 | 0 |
| Sync | 9 | 0 | 是 | 116 | 10.37 | 0 |
| Async / replace | 0 | 0 | 是 | 79 | 5.43 | 0 |
| Async / replace | 1 | 0 | 是 | 113 | 8.18 | 0 |
| Async / replace | 2 | 0 | 是 | 99 | 7.04 | 0 |
| Async / replace | 3 | 0 | 是 | 90 | 6.51 | 0 |
| Async / replace | 5 | 0 | 是 | 90 | 6.56 | 0 |
| Async / replace | 6 | 0 | 是 | 104 | 8.05 | 0 |
| Async / replace | 7 | 0 | 是 | 112 | 8.43 | 3 |
| Async / replace | 8 | 0 | 是 | 104 | 7.30 | 0 |
| Async / replace | 9 | 0 | 是 | 109 | 8.21 | 0 |
| Blend | 0 | 0 | 是 | 82 | 5.98 | 0 |
| Blend | 1 | 0 | 是 | 107 | 7.54 | 0 |
| Blend | 2 | 0 | 是 | 97 | 6.71 | 0 |
| Blend | 3 | 0 | 是 | 88 | 6.43 | 0 |
| Blend | 5 | 0 | 是 | 94 | 7.09 | 0 |
| Blend | 6 | 0 | 是 | 105 | 7.95 | 0 |
| Blend | 7 | 0 | 是 | 113 | 8.93 | 0 |
| Blend | 8 | 0 | 是 | 96 | 6.74 | 0 |
| Blend | 9 | 0 | 是 | 111 | 8.57 | 0 |

</details>

<details class="benchmark-archive"><summary>LIBERO Spatial · Orin / Thor 本机与协同推理 · 原始全案例（含失败） · 静态图表与明细</summary>

## LIBERO Spatial · Orin / Thor 本机与协同推理 · 原始全案例（含失败）

全案例记录 · 包含失败回合

| 设备 / 模式 | 原始成功 / 总数 | 执行步数 | 任务总耗时 / s | 平均推理响应时间¹ / ms | 推理响应时间 p95¹ / ms | 控制间隔 p95 / ms | hold 步 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 10/10 | 1002 | 81.91 | 124.78 | 127.54 | 190.34 | 0 |
| Thor local | 9/10 | 1118 | 33.38 | 31.05 | 33.22 | 56.34 | 0 |
| Sync | 9/10 | 1122 | 92.44 | 130.97 | 284.81 | 165.58 | 0 |
| Async / replace | 10/10 | 1026 | 74.78 | 115.03 | 241.70 | 82.45 | 3 |
| Blend | 10/10 | 1021 | 75.08 | 117.63 | 230.05 | 81.64 | 0 |

![LIBERO Spatial · Orin / Thor 本机与协同推理 · 原始全案例（含失败） 四项指标](../../assets/benchmarks/libero-spatial-20261017.svg)

- Orin / Thor 本机为 2026-10-17 运行；远程 Sync / Async / Blend 沿用 2026-10-16 的记录。历史分组保留，不跨运行合并样本。
- 同为 LIBERO Spatial、10 个任务各 1 次、seed 7、BF16、chunk 12。本机无墙钟限频，远程为 20 Hz 上限；远程重规划间隔 4 步、融合窗口 3 步、额外延迟 0。
- Orin 本机成功 10/10、1002 步；Thor 本机成功 9/10、1118 步，task 4 失败。远程 Sync 同样在 task 4 失败；各模式轨迹与执行步数不同，总耗时差不等于纯模型加速。
- 各次运行来自不同代码提交与运行时刻；本机 metadata 未记录 checkpoint SHA-256，不能仅凭文件名确认与远程权重一致。
- Orin 板卡 metadata 为 Orin NX Engineering Reference Developer Kit，与项目 Orin Nano 标注存在差异，结果保留 Orin 泛称。

### 调度与调用明细

| 模式 | 调用总数 / 过滤后 | 首次推理平均响应时间 / ms | 首段后阻塞 / s | 推理与 env.step 重叠比例 | drain / s | 指令变化 L2 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 88 / 78 | 323.14 | — | — | — | — |
| Thor local | 97 / 87 | 90.81 | — | — | — | — |
| Sync | 97 / 87 | 167.03 | 11.452 | 0.00 | 0.005 | 0.205 |
| Async / replace | 255 / 245 | 120.76 | 0.000 | 94.19 | 0.013 | 0.207 |
| Blend | 258 / 248 | 136.92 | 0.000 | 93.84 | 0.077 | 0.198 |

重叠比例单位为 %；L2 是相邻六维相对指令差值，混合了平移/旋转单位，不是物理 jerk。

### 推理耗时构成

![本机完整调用与协同推理各阶段耗时](../../assets/benchmarks/libero-spatial-20261017-stages.svg)

[下载 SVG](../../assets/benchmarks/libero-spatial-20261017-stages.svg) · [下载 PNG](../../assets/benchmarks/libero-spatial-20261017-stages.png)

本机显示完整调用；协同模式按同一过滤样本分解，各阶段均值之和等于平均响应。p95 独立统计。完整口径见[数据维护说明](./benchmark-data.md)。

| 协同模式 | Orin 预处理 | 编码压缩 | Thor 解码/排队 | Thor 推理 | HTTP/传输 | 其他开销 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sync | 6.98 | 6.79 | 2.72 | 28.75 | 85.49 | 0.24 |
| Async / replace | 11.14 | 7.54 | 2.68 | 27.94 | 65.41 | 0.32 |
| Blend | 10.35 | 7.29 | 2.67 | 27.84 | 69.17 | 0.31 |

单位：ms。HTTP/传输包含接收等待与系统开销；阶段不足或样本不齐时不推测分解。

### 数据来源

| 来源运行 | 配置 | 每回合排除调用数 |
| --- | --- | ---: |
| `orin_to_thor_async_libero_spatial_20261016T224546_700348+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| `orin_libero_spatial_bf16_20261017T180050_872432+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| `thor_libero_spatial_bf16_20261017T180559_765357+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |

### 逐任务结果

| 模式 | task ID | episode | 成功 | 步数 | 任务耗时 / s | hold 步 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Orin local | 0 | 0 | 是 | 76 | 7.81 | 0 |
| Orin local | 1 | 0 | 是 | 111 | 8.52 | 0 |
| Orin local | 2 | 0 | 是 | 90 | 7.04 | 0 |
| Orin local | 3 | 0 | 是 | 80 | 6.18 | 0 |
| Orin local | 4 | 0 | 是 | 134 | 10.51 | 0 |
| Orin local | 5 | 0 | 是 | 95 | 7.69 | 0 |
| Orin local | 6 | 0 | 是 | 100 | 8.24 | 0 |
| Orin local | 7 | 0 | 是 | 107 | 9.13 | 0 |
| Orin local | 8 | 0 | 是 | 96 | 7.47 | 0 |
| Orin local | 9 | 0 | 是 | 113 | 9.33 | 0 |
| Thor local | 0 | 0 | 是 | 79 | 2.62 | 0 |
| Thor local | 1 | 0 | 是 | 118 | 3.40 | 0 |
| Thor local | 2 | 0 | 是 | 95 | 2.54 | 0 |
| Thor local | 3 | 0 | 是 | 87 | 2.51 | 0 |
| Thor local | 4 | 0 | 否 | 220 | 6.42 | 0 |
| Thor local | 5 | 0 | 是 | 93 | 2.85 | 0 |
| Thor local | 6 | 0 | 是 | 105 | 3.32 | 0 |
| Thor local | 7 | 0 | 是 | 113 | 3.50 | 0 |
| Thor local | 8 | 0 | 是 | 94 | 2.66 | 0 |
| Thor local | 9 | 0 | 是 | 114 | 3.56 | 0 |
| Sync | 0 | 0 | 是 | 80 | 6.30 | 0 |
| Sync | 1 | 0 | 是 | 114 | 8.90 | 0 |
| Sync | 2 | 0 | 是 | 96 | 7.78 | 0 |
| Sync | 3 | 0 | 是 | 86 | 7.53 | 0 |
| Sync | 4 | 0 | 否 | 220 | 17.68 | 0 |
| Sync | 5 | 0 | 是 | 96 | 7.77 | 0 |
| Sync | 6 | 0 | 是 | 108 | 9.15 | 0 |
| Sync | 7 | 0 | 是 | 112 | 9.74 | 0 |
| Sync | 8 | 0 | 是 | 94 | 7.22 | 0 |
| Sync | 9 | 0 | 是 | 116 | 10.37 | 0 |
| Async / replace | 0 | 0 | 是 | 79 | 5.43 | 0 |
| Async / replace | 1 | 0 | 是 | 113 | 8.18 | 0 |
| Async / replace | 2 | 0 | 是 | 99 | 7.04 | 0 |
| Async / replace | 3 | 0 | 是 | 90 | 6.51 | 0 |
| Async / replace | 4 | 0 | 是 | 126 | 9.06 | 0 |
| Async / replace | 5 | 0 | 是 | 90 | 6.56 | 0 |
| Async / replace | 6 | 0 | 是 | 104 | 8.05 | 0 |
| Async / replace | 7 | 0 | 是 | 112 | 8.43 | 3 |
| Async / replace | 8 | 0 | 是 | 104 | 7.30 | 0 |
| Async / replace | 9 | 0 | 是 | 109 | 8.21 | 0 |
| Blend | 0 | 0 | 是 | 82 | 5.98 | 0 |
| Blend | 1 | 0 | 是 | 107 | 7.54 | 0 |
| Blend | 2 | 0 | 是 | 97 | 6.71 | 0 |
| Blend | 3 | 0 | 是 | 88 | 6.43 | 0 |
| Blend | 4 | 0 | 是 | 128 | 9.14 | 0 |
| Blend | 5 | 0 | 是 | 94 | 7.09 | 0 |
| Blend | 6 | 0 | 是 | 105 | 7.95 | 0 |
| Blend | 7 | 0 | 是 | 113 | 8.93 | 0 |
| Blend | 8 | 0 | 是 | 96 | 6.74 | 0 |
| Blend | 9 | 0 | 是 | 111 | 8.57 | 0 |

</details>

<details class="benchmark-archive"><summary>LIBERO Spatial · 2026-10-16 · 原始全案例（含失败） · 静态图表与明细</summary>

## LIBERO Spatial · 2026-10-16 · 原始全案例（含失败）

全案例记录 · 包含失败回合

| 设备 / 模式 | 原始成功 / 总数 | 执行步数 | 任务总耗时 / s | 平均推理响应时间¹ / ms | 推理响应时间 p95¹ / ms | 控制间隔 p95 / ms | hold 步 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 10/10 | 1002 | 94.34 | 148.51 | 189.49 | — | — |
| Sync | 9/10 | 1122 | 92.44 | 130.97 | 284.81 | 165.58 | 0 |
| Async / replace | 10/10 | 1026 | 74.78 | 115.03 | 241.70 | 82.45 | 3 |
| Blend | 10/10 | 1021 | 75.08 | 117.63 | 230.05 | 81.64 | 0 |

![LIBERO Spatial · 2026-10-16 · 原始全案例（含失败） 四项指标](../../assets/benchmarks/libero-spatial-20261016.svg)

- 10 个任务各 1 次，seed 7、BF16、chunk 12；远程重规划间隔 4 步、融合窗口 3 步、额外延迟 0。
- Sync 在 task 4 失败，其余任务成功；Async 和 Blend 各 10/10 成功。总时间差含轨迹和完成步数变化。
- 本组只有 Orin 本机数据，尚无 Thor 本机独立运行。旧本机记录缺少控制时间戳，相关指标标为未记录。
- 本机与远程来自不同代码提交和运行时刻；本机未记录 checkpoint SHA-256，权重一致性不能仅凭文件名确认。
- 板卡 metadata 报告 Orin NX Engineering Reference Developer Kit，与项目 Orin Nano 标注存在差异；本页用 Orin 泛称并保留原始值。

### 调度与调用明细

| 模式 | 调用总数 / 过滤后 | 首次推理平均响应时间 / ms | 首段后阻塞 / s | 推理与 env.step 重叠比例 | drain / s | 指令变化 L2 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 88 / 78 | 627.23 | — | — | — | — |
| Sync | 97 / 87 | 167.03 | 11.452 | 0.00 | 0.005 | 0.205 |
| Async / replace | 255 / 245 | 120.76 | 0.000 | 94.19 | 0.013 | 0.207 |
| Blend | 258 / 248 | 136.92 | 0.000 | 93.84 | 0.077 | 0.198 |

重叠比例单位为 %；L2 是相邻六维相对指令差值，混合了平移/旋转单位，不是物理 jerk。

### 推理耗时构成

![本机完整调用与协同推理各阶段耗时](../../assets/benchmarks/libero-spatial-20261016-stages.svg)

[下载 SVG](../../assets/benchmarks/libero-spatial-20261016-stages.svg) · [下载 PNG](../../assets/benchmarks/libero-spatial-20261016-stages.png)

本机显示完整调用；协同模式按同一过滤样本分解，各阶段均值之和等于平均响应。p95 独立统计。完整口径见[数据维护说明](./benchmark-data.md)。

| 协同模式 | Orin 预处理 | 编码压缩 | Thor 解码/排队 | Thor 推理 | HTTP/传输 | 其他开销 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sync | 6.98 | 6.79 | 2.72 | 28.75 | 85.49 | 0.24 |
| Async / replace | 11.14 | 7.54 | 2.68 | 27.94 | 65.41 | 0.32 |
| Blend | 10.35 | 7.29 | 2.67 | 27.84 | 69.17 | 0.31 |

单位：ms。HTTP/传输包含接收等待与系统开销；阶段不足或样本不齐时不推测分解。

### 数据来源

| 来源运行 | 配置 | 每回合排除调用数 |
| --- | --- | ---: |
| `orin_libero_spatial_bf16_20261016T211904_081157+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| `orin_to_thor_async_libero_spatial_20261016T224546_700348+0800` | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |

### 逐任务结果

| 模式 | task ID | episode | 成功 | 步数 | 任务耗时 / s | hold 步 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Orin local | 0 | 0 | 是 | 76 | 9.06 | — |
| Orin local | 1 | 0 | 是 | 111 | 9.29 | — |
| Orin local | 2 | 0 | 是 | 90 | 8.56 | — |
| Orin local | 3 | 0 | 是 | 80 | 10.05 | — |
| Orin local | 4 | 0 | 是 | 134 | 14.14 | — |
| Orin local | 5 | 0 | 是 | 95 | 8.25 | — |
| Orin local | 6 | 0 | 是 | 100 | 8.71 | — |
| Orin local | 7 | 0 | 是 | 107 | 9.29 | — |
| Orin local | 8 | 0 | 是 | 96 | 7.52 | — |
| Orin local | 9 | 0 | 是 | 113 | 9.47 | — |
| Sync | 0 | 0 | 是 | 80 | 6.30 | 0 |
| Sync | 1 | 0 | 是 | 114 | 8.90 | 0 |
| Sync | 2 | 0 | 是 | 96 | 7.78 | 0 |
| Sync | 3 | 0 | 是 | 86 | 7.53 | 0 |
| Sync | 4 | 0 | 否 | 220 | 17.68 | 0 |
| Sync | 5 | 0 | 是 | 96 | 7.77 | 0 |
| Sync | 6 | 0 | 是 | 108 | 9.15 | 0 |
| Sync | 7 | 0 | 是 | 112 | 9.74 | 0 |
| Sync | 8 | 0 | 是 | 94 | 7.22 | 0 |
| Sync | 9 | 0 | 是 | 116 | 10.37 | 0 |
| Async / replace | 0 | 0 | 是 | 79 | 5.43 | 0 |
| Async / replace | 1 | 0 | 是 | 113 | 8.18 | 0 |
| Async / replace | 2 | 0 | 是 | 99 | 7.04 | 0 |
| Async / replace | 3 | 0 | 是 | 90 | 6.51 | 0 |
| Async / replace | 4 | 0 | 是 | 126 | 9.06 | 0 |
| Async / replace | 5 | 0 | 是 | 90 | 6.56 | 0 |
| Async / replace | 6 | 0 | 是 | 104 | 8.05 | 0 |
| Async / replace | 7 | 0 | 是 | 112 | 8.43 | 3 |
| Async / replace | 8 | 0 | 是 | 104 | 7.30 | 0 |
| Async / replace | 9 | 0 | 是 | 109 | 8.21 | 0 |
| Blend | 0 | 0 | 是 | 82 | 5.98 | 0 |
| Blend | 1 | 0 | 是 | 107 | 7.54 | 0 |
| Blend | 2 | 0 | 是 | 97 | 6.71 | 0 |
| Blend | 3 | 0 | 是 | 88 | 6.43 | 0 |
| Blend | 4 | 0 | 是 | 128 | 9.14 | 0 |
| Blend | 5 | 0 | 是 | 94 | 7.09 | 0 |
| Blend | 6 | 0 | 是 | 105 | 7.95 | 0 |
| Blend | 7 | 0 | 是 | 113 | 8.93 | 0 |
| Blend | 8 | 0 | 是 | 96 | 6.74 | 0 |
| Blend | 9 | 0 | 是 | 111 | 8.57 | 0 |

</details>

## 口径与追加方法

见[数据维护说明](./benchmark-data.md)。每组保留独立运行和逐任务结果，不自动合并不同 seed、任务集、设备或延迟设置。原始评测文件位于可提交的 `outputs/`，精简数据目录记录来源文件名及 SHA-256，重建网页无需访问原始文件。
