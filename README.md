# TurboVLA-SplitInfer

基于预训练 TurboVLA 的 LIBERO 双设备推理：**Orin 负责仿真、图像/状态预处理和压缩，Thor 负责全部神经网络推理**，动作返回 Orin 执行。支持本机基准，以及同步、异步替换、异步融合三种远程模式。

## 环境与资源

使用 Python 3.10，先安装适配设备的 CUDA PyTorch，再安装项目依赖：

```bash
pip install -e '.[libero,split]'
```

另行安装 [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)。Thor 或本机推理设备需准备 [TurboVLA 权重](https://huggingface.co/H-EmbodVis/TurboVLA)、DINOv3 ViT-B 和 BERT base uncased；远程模式的 Orin 无需模型权重。在线评测需要 LIBERO 的 BDDL、初始状态和 assets，不要求下载演示数据。

## 运行

在仓库根目录、对应设备的 Python 环境中执行：

```bash
# Thor：启动模型服务，默认端口 8765
bash scripts/libero/serve_thor.sh

# Orin：检查配置和服务，再运行三种模式
bash scripts/libero/run_async_benchmark.sh --preflight
bash scripts/libero/run_async_benchmark.sh

# 单任务、指定模式；replace 即异步直接替换
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes sync
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes replace
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes blend

# Orin 或 Thor：全部模型在当前设备推理的本机基准
bash scripts/libero/run_local_benchmark.sh
```

| 模式 | 调度方式 |
| --- | --- |
| `sync` | 执行完当前动作块，再阻塞请求下一块 |
| `replace` | 执行期间后台预测，按已执行步数裁掉过期前缀，替换未来动作 |
| `blend` | 同样后台预测和对齐，在新旧动作重叠窗口内渐变切换 |

默认动作块 12 步、每 4 步尝试重规划、融合窗口 3 步，最多一个请求在途。融合仅处理前 6 维相对位姿指令，新动作权重为 `1/3 → 2/3 → 1`；夹爪保持离散切换。缓冲区为空时保持夹爪并执行零手臂增量，记录为 `hold_steps`。这是推理阶段的融合实验，不是 RTC 实现。

## 配置

- **远程评测**：[async_benchmark.yaml](experiments/libero/configs/async_benchmark.yaml)。`paths` / `libero_paths` 配置 LIBERO 代码、资源与数据目录；`evaluation` 配置 Thor URL、任务、精度、视频等；`experiment` 配置模式、重规划和融合窗口；`benchmark` 配置输出目录及首次调用筛选数。
- **本机评测**：[local_benchmark.yaml](experiments/libero/configs/local_benchmark.yaml)。另需配置 checkpoint、DINOv3、BERT 和统计文件路径。
- **Thor 服务**：[serve_thor.sh](scripts/libero/serve_thor.sh)。默认 checkpoint 为 `pretrained/TurboVLA/checkpoints/libero/turbovla_libero.pth`；`DINOV3_PATH`、`BERT_PATH`、`THOR_HOST`、`THOR_PORT` 可覆盖模型路径和监听地址，`--ckpt_path` 可覆盖权重路径。

默认 `libero_spatial` 全部任务、每任务每模式 1 次、seed 7、BF16、EGL。`task_ids: "0,1,2"` 可缩小测试范围。`chunk_size` 和精度须与 Thor 服务一致。统计文件为 [libero_all4_stats.json](experiments/libero/configs/libero_all4_stats.json)，key 为 `libero_all4_no_noops`。

相对路径以仓库根目录为准，命令行参数优先。`THOR_URL` / `LIBERO_ROOT` 可覆盖远程配置，`TURBOVLA_PYTHON` 可指定脚本解释器。每次运行生成独立 LIBERO 路径配置。可复制 YAML 为 `*.local.yaml`，通过 `--config` 指定；本机配置被 Git 忽略。

## 关键代码

| 位置 | 职责 |
| --- | --- |
| [scripts/libero/benchmark_async.py](scripts/libero/benchmark_async.py) | 统一远程入口、配置、三模式对比与报告导出 |
| [turbovla/evaluation/async_rollout.py](turbovla/evaluation/async_rollout.py) · `run_episode()` | 后台预测、单请求调度、动作执行与缓冲区耗尽处理 |
| 同文件 · `ActionTimeline.merge()` | 新旧动作按控制步对齐、`replace` 替换、`blend` 融合 |
| 同文件 · `save_realtime_video()` | 按墙钟时间导出，标注等待、后台推理及保持状态 |
| [turbovla/split/](turbovla/split/) | `client.py`：Orin 预处理与请求；`server.py`：Thor 推理；`protocol.py`：张量编码与无损压缩 |
| [scripts/libero/benchmark_local.py](scripts/libero/benchmark_local.py) / [benchmark_common.py](scripts/libero/benchmark_common.py) | 本机评测 / 公共配置、设备识别及统计工具 |
| [turbovla/evaluation/suite_policy.py](turbovla/evaluation/suite_policy.py) | LIBERO 策略适配、动作反归一化 |
| [turbovla/models/action_head.py](turbovla/models/action_head.py) | ACT 风格动作解码器，一次输出完整动作块 |

## 结果与验证

结果自动按设备和时间戳保存：远程在 `outputs/evaluation/async/`，本机在 `outputs/evaluation/local/`。远程每个模式包含原始 JSON、summary、逐请求/逐控制步 CSV 和视频，另有 comparison 与运行 metadata。

普通视频按控制步以 20 FPS 回放；`*_realtime.mp4` 保留实际等待时间。`filtered_calls` 默认排除每个 episode 的首次请求，原始记录保留。异步重点比较成功率、控制间隔 p95、`hold_steps` 和总用时；推理与执行重叠，不能用总用时减推理耗时推导其他耗时。配置中的 20Hz 是墙钟频率上限，不保证仿真达到该速度。

```bash
PYTHONPATH=third_party/vla_adapter:. python -m unittest discover -s tests -v
```

[benchmark_transport.py](scripts/libero/benchmark_transport.py) 用于固定观测的传输测速；[check_split_parity.py](scripts/libero/check_split_parity.py) 验证直接推理与 HTTP 返回动作一致；[summarize_split.py](scripts/libero/summarize_split.py) 可补算历史同步结果。权重、数据集、输出和视频均不提交 Git。

## 论文引用

[TurboVLA: Real-Time Vision-Language-Action Model at 32 Hz on an RTX 4090 with <1 GB VRAM](https://arxiv.org/abs/2607.27205). arXiv:2607.27205, 2026.

[上游代码](https://github.com/H-EmbodVis/TurboVLA) · [项目许可证](LICENSE) · [LIBERO 评测适配来源许可](third_party/licenses/VLA-Adapter.txt)
