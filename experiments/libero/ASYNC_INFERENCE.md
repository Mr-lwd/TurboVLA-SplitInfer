# 统一远程评测：同步、异步替换与异步融合

远程评测复用预训练权重，在推理调度层比较三种模式。模型、训练流程、
`evaluate.py` 和原同步 rollout 保持不变。统一入口为 `scripts/libero/run_async_benchmark.sh`，
调度实现位于 `turbovla/evaluation/async_rollout.py`。

目前实验入口针对 **Orin → Thor split**：Orin 主线程执行 LIBERO，后台线程完成
Orin 的图像/状态预处理、无损压缩和 HTTP 请求，Thor 执行全部神经网络层。
一次最多一个请求在途，不积压历史观测。不会在 Orin 加载整套权重。

## 运行与配置

Thor 按原流程启动服务：

```bash
conda activate turbovla
bash scripts/libero/serve_thor.sh
```

Orin 运行统一评测：

```bash
conda activate turbovla-libero
# 只检查配置、LIBERO 资源路径和服务元数据，不执行 rollout
bash scripts/libero/run_async_benchmark.sh --preflight
# 默认全部任务，每任务三种模式各一次，保存两类视频
bash scripts/libero/run_async_benchmark.sh
```

所有路径和参数都在 [`configs/async_benchmark.yaml`](configs/async_benchmark.yaml) 中配置，无需修改 Python：

| 区块 | 配置内容 |
| --- | --- |
| `paths` | LIBERO 代码根目录，支持路径或候选路径列表 |
| `libero_paths` | benchmark、BDDL、初始状态、assets、演示数据目录 |
| `benchmark` | 输出根目录、每个 episode 排除的首次调用数 |
| `evaluation` | Thor URL、压缩方式、精度、任务、次数、seed、chunk、视频等 |
| `experiment` | 模式列表、重规划间隔、融合窗口、节拍上限、额外延迟 |

相对路径均以仓库根目录为准，支持环境变量；`libero_paths` 支持 `${libero_root}`。
LIBERO 运行配置写入每次输出目录，不修改全局 `~/.libero/config.yaml`。
参数优先级为命令行 > 环境变量（对应字段）> YAML > 原评测器默认值。
`THOR_URL` 可覆盖服务地址，`LIBERO_ROOT` 可覆盖代码根目录。
输出使用 `benchmark.output_root` 或 `--output_root`；筛选数量使用
`benchmark.exclude_first_calls` 或 `--exclude_first_calls`。可用
`--libero_datasets`、`--libero_assets` 等临时覆盖 LIBERO 资源路径。

需要本机配置时复制完整 YAML，再通过 `--config` 指定；`*.local.yaml` 已被 Git 忽略。
旧的 `base_config` 继承格式已移除，旧本机配置应将路径、服务地址等迁入这份完整配置，
并将原 `experiment.output_root` 移到 `benchmark.output_root`。

```bash
cp experiments/libero/configs/async_benchmark.yaml experiments/libero/configs/orin_async.local.yaml
bash scripts/libero/run_async_benchmark.sh --config experiments/libero/configs/orin_async.local.yaml
# 原同步 split 基线也通过同一入口运行
bash scripts/libero/run_async_benchmark.sh --modes sync
```

源码分工：`benchmark_async.py` 负责统一远程评测，`benchmark_local.py` 负责本机评测，
`benchmark_common.py` 提供公共配置、设备识别与报告工具。
`turbovla/split/` 是三种远程模式共享的通信层，`serve_thor.sh` 仍负责启动模型服务。
`benchmark_transport.py` / `check_split_parity.py` 保留用于传输性能与动作一致性检查；
`summarize_split.py` 仅补算历史同步结果，不用于运行新评测。

```bash
# 单任务三模式对比，指定服务器
bash scripts/libero/run_async_benchmark.sh --task_ids 0 \
  --remote_policy_url http://192.168.123.38:8765
# 全部任务，每任务三个相同初始状态，窗口设为 4 步
bash scripts/libero/run_async_benchmark.sh --task_ids "" \
  --num_trials_per_task 3 --replan_every_steps 4 --blend_steps 4
# 对全部模式增加 200ms 请求延迟，测试延迟容忍能力
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --extra_delay_s 0.2
# 只比较两种异步策略
bash scripts/libero/run_async_benchmark.sh --modes replace blend
```

`chunk_size` 必须与 Thor 服务一致，且等于 `num_open_loop_steps`。
重规划间隔必须小于 chunk，融合窗口为 1～chunk 步。当前只支持 relative 控制。
每个任务/初始状态下随机打乱模式顺序（由 seed 确定），各模式重新创建并设置相同
种子的环境、使用同一初始状态。首次预测均阻塞，用于建立初始动作缓冲区。

## 三种模式

| 模式 | 请求时机 | 收到预测后的处理 |
| --- | --- | --- |
| `sync` | 执行完当前 chunk 后阻塞请求 | 完整执行新 chunk，与原同步策略相同 |
| `replace` | 默认每执行 4 步、有空闲 worker 时采样新观测 | 裁掉过期前缀，直接替换未来动作 |
| `blend` | 与 replace 相同 | 裁掉过期前缀，在新旧预测重叠的前 3 步内渐变 |

对齐依据是 **观测采样后实际执行的控制步数**。例如，使用第 4 步动作执行前的观测
预测 12 步，结果在第 6 步动作执行前可用，则丢弃新预测的前 2 步，从第 3 个动作开始。
旧预测尾部被新预测覆盖，不能在新预测用完后又执行更旧的尾部。

不会将网络耗时除以 50ms 后取整来裁剪：LIBERO 中一次 `env.step()` 推进一个控制步，
Orin 仿真/渲染可能慢于墙钟 20Hz，也可能在初次推理时暂停。`control_hz: 20` 只是
墙钟执行频率上限；慢于这个频率时不跳步、不成批追赶。实际物理机器应根据控制器的
执行时间戳重新定义对齐，不能直接把此实验的 LIBERO tick 当作真实机器时间。

融合窗口大小取配置窗口与实际重叠长度的较小值。第 i 个窗口槽位的权重为
`alpha = (i + 1) / window`：前 6 维相对位姿指令使用
`(1-alpha)*old + alpha*new`，夹爪在 alpha < 0.5 时取旧值，否则取新值，不做连续插值。
新旧动作在同一个未来控制步上融合；不混合错位的数组索引。

缓冲区耗尽时，执行零相对手臂增量、保持上一夹爪指令，并记录 `hold_steps`。
如果返回的整个 chunk 已过期，丢弃并用最新观测继续请求。后台异常会终止实验并记录
失败，不会静默忽略。episode 结束后等待最后一个在途请求完成，随后再 reset/切换模式；
这段 drain 单独计时，不算任务执行时间。

## 输出和指标

输出位于 `outputs/evaluation/async/<客户端>_to_<服务端>_async_<套件>_<时间戳>/`。
设备从 GPU/板卡自动识别，所有结果和视频沿用仓库已有忽略规则。

- `*_comparison.json/csv`：三种模式汇总。
- `*_<模式>_summary.json`：成功率、实际执行步数、完整 rollout 时间、控制间隔分布、
  全部/首次/过滤后推理耗时、bootstrap/后续阻塞等待、hold、过期 chunk、裁剪步数、
  融合槽位数、推理与 `env.step()` 实际重叠时长、episode 后 drain 时长，以及
  客户端/网络/Thor 各阶段分布、传输字节数和服务进程显存峰值。
- `*_<模式>.json`、`*_calls.csv`、`*_steps.csv`：逐 episode、逐请求、逐步的动作与计时，
  包含客户端预处理/编码、传输和 Thor 各阶段原始 `remote` 指标。
- `*_metadata.json`：软硬件、服务器权重 SHA256、最终参数、模式运行顺序及运行状态。
- `<模式>/videos/*_realtime.mp4`：根据墙钟时间导出，区分 `INFERENCE WAIT`、
  `CONTROL + BACKGROUND INFERENCE` 和 `HOLD / BUFFER EMPTY`，展示最终观察帧。
  普通 `.mp4` 仍为每控制步一帧的 20FPS 回放。计时排除 reset、settling 和视频编码；
  视频时间量化误差不超过约 0.1 秒。后台 drain 不进入任务视频。

`filtered_calls` 默认排除**每个 episode 的第一次请求**，原始请求始终保留。
`duration_s` 包含可选的人工延迟；`policy_duration_s` 排除人工延迟。
重叠统计取真实 worker 区间与 `env.step()` 区间的交集；只描述执行时间重叠，
不能据此声称 GPU kernel 同时执行。异步模式下不能用“墙钟时间减推理总时间”推导
非推理耗时。`worker_drain_after_episode_s` 必须另看，因为任务结束时可能还在推理。

`oldest_observation_age` 使用动作来源观测到执行时的控制步数；混合动作取最老的贡献来源。
`arm_action_changes` 为相邻两条六维相对指令差值的 L2，位置与旋转单位混合，
**不是物理加速度或 jerk**；用于同设置下辅助观察指令变化，不能代替轨迹质量检查。

## 如何解读结果

这个版本无需重新训练，能够验证边执行边预测、按时间对齐和短窗口融合。
但预训练模型没有针对延迟或执行中的旧动作序列训练：新预测的前缀假设可能与实际执行
轨迹不同，简单裁剪和融合不保证提高成功率。它是推理阶段的调度实验，并非训练过的
delay-conditioned / RTC 模型。

异步每 4 步重规划，同步每 12 步请求，因此请求数量、闭环反馈频率和动作轨迹都会改变。
评估时同时比较成功率、完成步数、控制间隔 p95、阻塞/hold、动作变化和总用时。
更短的 rollout 可能来自更少的完成步数，也可能只是更早失败，不能只比较总秒数。
若 async 的每次请求反而变慢，应检查 Orin 预处理与仿真渲染争用 CPU/内存的影响。
少量任务的一次成功只能作为冒烟验证，正式结论需要相同配置下更多任务和初始状态。

单元测试（不需要 GPU、LIBERO 环境或在线 Thor 服务）：

```bash
PYTHONPATH=third_party/vla_adapter:. python -m unittest discover -s tests -v
```

## 2026-10-16 实机验证

Orin NX → Thor、BF16、zstd_shuffle、keep-alive、chunk 12、每 4 步重规划、
3 步融合、seed 7。`libero_spatial` 的任务 0/1/2 各一个初始状态：

| 模式 | 成功 | 执行步数 | 总 rollout 时间 | 控制间隔 p95 | 首段之后的阻塞等待 | 保持步 |
| --- | --- | --- | --- | --- | --- | --- |
| sync | 3/3 | 290 | 22.558s | 155.61ms | 2.716s | 0 |
| replace | 3/3 | 285 | 20.166s | 76.92ms | 0s | 0 |
| blend | 3/3 | 284 | 20.157s | 78.63ms | 0s | 0 |

此样本中总时间减少约 10.6%，其中也包括完成步数减少；主要观察是消除了 chunk 边界的
阻塞，使控制间隔更均匀。两种异步模式约 92% 的 worker 时间与 `env.step()` 重叠。
sync/replace/blend 分别调用 25/70/72 次，异步用更多推理换取更频繁的反馈。
Orin 实际执行间隔约 69ms，未达到 20Hz。

相邻手臂指令差值 L2 的 p95 分别为 0.198/0.213/0.207，最大值分别为
0.658/0.463/0.359。融合在该样本中降低了最大跳变，但不能说它全面改善了动作平滑度。

另在任务 0 上为**每次请求增加 200ms**：

| 模式 | 成功 | 步数 | rollout 时间 | 控制间隔 p95 | 保持步 |
| --- | --- | --- | --- | --- | --- |
| sync | 1/1 | 80 | 7.392s | 361.70ms | 0 |
| replace | 1/1 | 91 | 6.346s | 72.05ms | 15 |
| blend | 1/1 | 89 | 6.613s | 82.65ms | 1 |

直接替换仍按时发出控制指令，但其中 15 步因缓冲区为空而保持。其过滤后请求平均
351ms、最大 551ms；融合相应为 308ms、509ms。请求延迟存在波动，因此不能把两次运行的
hold 差别全部归因于融合本身，也不能只看控制间隔就认定机器人始终在有效运动。
调大延迟后应同时检查 hold、轨迹和成功率，再决定是否提前重规划或调整窗口。

本机原始结果（不提交 Git）：

- `outputs/evaluation/async/orin_to_thor_async_libero_spatial_20261016T222612_976488+0800/`
- `outputs/evaluation/async/orin_to_thor_async_libero_spatial_20261016T223110_996335+0800/`

共完成 12 次 rollout，生成 24 个视频；全部带墙钟时间的视频均已核对时长。
28 项单元测试通过。实测临时使用 8766 端口，测试后已停止该服务；默认复跑仍使用
YAML 中的 8765 服务地址。
