# 验证与结果

验证分为代码行为、模型数值一致性和实机任务表现三层，分别对应单元测试、推理路径对比与设备端任务评测。

## 代码行为

在仓库根目录运行已有测试：

```bash
PYTHONPATH=third_party/vla_adapter:. python -m unittest discover -s tests -v
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = 'third_party/vla_adapter;.'
python -m unittest discover -s tests -v
```

2026-10-17 在本地 `turbovla-libero` 环境运行：**33 项通过**。测试通过 mock / fake policy 与本机 HTTP 核验协议、调度和报告逻辑。

| 测试文件 | 核验内容 |
| --- | --- |
| `test_split_inference.py` | BF16/FP32 位保真、可用 codec、HTTP 往返、复用连接、服务实例变化、非法载荷 |
| `test_async_inference.py` | replace 对齐、blend 权重、过期块、观测快照、单请求、hold、退出 drain |
| `test_async_benchmark.py` | 三模式入口、CLI 覆盖、preflight、失败状态、报告 |
| `test_local_benchmark.py` | 本机配置、统计、路径优先级、结果命名 |
| `test_legacy_split_reports.py` | 历史报告补算及缺失指标处理 |
| `test_libero_video_timing.py` | 真实等待时长、终止帧与视频时间轴 |

## 模型数值一致性

Thor 启动服务后，在同一设备比较直接推理与 HTTP 路径：

```bash
python scripts/libero/check_split_parity.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --ckpt_path /path/to/turbovla_libero.pth \
  --dinov3_path /path/to/DINOv3 \
  --bert_path /path/to/bert-base-uncased
```

该脚本检查 checkpoint SHA-256，默认按 BF16 比较直接推理与 HTTP 推理的 3 组输入，要求 `rtol=0, atol=1e-6`。

## 固定观测通信测试

准备 NPZ，包含 `primary` / `wrist`：uint8 `[N,256,256,3]`，`state`：float32 `[N,8]`，`instruction`：字符串 `[N]`。

```bash
python scripts/libero/benchmark_transport.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --observations /path/to/observations.npz \
  --repetitions 30 --warmup 3
```

脚本对比压缩和 keep-alive，要求相同观测的返回动作严格相等。统计范围为通信与推理链路，任务成功率由完整 rollout 评测记录。

## 结果文件

远程运行存放于 `outputs/evaluation/async/<device_pair>_<suite>_<timestamp>/`。每个模式的结果文件位于运行目录根部，视频位于 `<mode>/videos/`。

| 文件后缀 | 用途 |
| --- | --- |
| `_metadata.json` | 解析后配置、软件与硬件、模型哈希、执行顺序、completed/failed 状态 |
| `_<mode>.json` | 原始 episode、动作、控制步、调用与等待 |
| `_<mode>_summary.json` | 每模式统计 |
| `_<mode>_calls.csv` / `_steps.csv` | 逐请求 / 逐步明细 |
| `_comparison.json` / `.csv` | 模式比较；失败时不应当作完整对比 |
| `*_realtime.mp4` | 保留实际等待、后台推理和 hold 的墙钟回放 |

## 指标解释

| 指标 | 解释 | 统计口径 |
| --- | --- | --- |
| `success_rate` | 成功 episode / 全部 episode | 同时报告任务数与重复次数 |
| `control_intervals.p95_ms` | 相邻动作开始时间间隔 p95 | 按实际动作时间戳统计，控制频率上限配置为 20 Hz |
| `hold_steps` | 缺少当前动作时的保持步数 | 与任务成功率、缓冲耗尽情况联合分析 |
| `round_trip_s` | 一次请求的往返时间 | 包含服务处理，并非纯网络延迟 |
| `transport_overhead_s` | 往返减服务总时间的残差 | 仍含 HTTP、socket、响应处理开销 |
| `filtered_calls` | 每 episode 排除指定首调用后统计 | 原始数据仍保留，不能选择性删慢样本 |
| `server_cuda_peak_*` | 服务进程存续期 allocator 峰值 | 包含加载、预热与历史请求；非当前 rollout 独占峰值 |
| `worker_drain_after_episode_s` | 结束后等待后台请求收尾 | 与 rollout 墙钟时间分开统计 |

阶段耗时存在嵌套，不可直接全部相加；异步推理与执行重叠，不可用总时间减累计推理时间推导“其余耗时”。

## 实机验收建议

保持 checkpoint、任务、初始状态、seed 和图像配置一致，记录两端功耗模式、温度与网络环境。逐步增加任务和重复次数，并加入延迟压力实验；同时报告成功率、p95、hold、过期动作块和总时长。达到什么门槛，应由实际场景需求确定。
