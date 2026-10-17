# 代码完整性

项目覆盖“配置 → 服务 → 客户端 → 调度 → 执行 → 报告 → 测试”的完整实验链路，各模块提供对应入口、配置与验证方法。

## 代码地图

```text
turbovla/
  models/       共用 TurboVLA：DINOv3、BERT、双向交互、ACT
  split/        Orin 客户端、Thor HTTP 服务、版本化张量协议
  evaluation/   策略适配、动作反归一化、三模式调度
  data/         LIBERO RLDS、混合套件、统计归一化
  training/     训练入口、优化器与 EMA
scripts/libero/ 基准入口、预检、通信测量、数值一致性、汇总
experiments/    LIBERO / RoboTwin 入口与配置
tests/          六个测试模块
third_party/    兼容运行时及保留许可证
docs-site/      本站源码与静态构建配置
assets/         原始架构图与图稿
```

## 从入口追到证据

| 能力 | 入口 / 实现 | 配置或资源 | 验证证据 |
| --- | --- | --- | --- |
| Thor 推理服务 | `serve_thor.sh` → `split/server.py` | checkpoint、DINOv3、BERT、stats | `/health`、服务日志、split 测试 |
| Orin 远程调用 | `split/client.py` | URL、精度、codec | HTTP fake-policy 往返测试 |
| 传输编码 | `split/protocol.py` | 固定形状与协议版本 | 位保真、截断、附加数据、非有限值测试 |
| 三模式实验 | `benchmark_async.py` → `async_rollout.py` | `async_benchmark.yaml` | 对齐 / 融合 / 失败传播测试及 comparison |
| 本机对照 | `benchmark_local.py` | `local_benchmark.yaml` | 本机入口与统计测试 |
| 模型输出一致性 | `check_split_parity.py` | 同一 checkpoint 与 stats | 在 Thor 比较两条推理路径，生成 parity JSON |
| 通信选型 | `benchmark_transport.py` | 固定观测 NPZ | 相同动作约束下比较各 codec |
| 训练与数据 | `training/`、`data/` | RLDS/TFDS、统计、初始化资源 | 数据处理、训练配方与训练入口 |
| RoboTwin 扩展 | `experiments/robotwin/` | 独立 all50 配置与外部 RoboTwin | 独立训练与评测流程 |

## 外部资源清单

| 仓库内提供 | 需要另行准备 |
| --- | --- |
| 模型实现、适配、服务、客户端、调度 | 模型权重及本地模型目录 |
| YAML/JSON 配置、LIBERO 统计 | LIBERO 代码、BDDL、初始状态和 assets |
| 单元测试与报告脚本 | JetPack、GPU 驱动、对应 PyTorch |
| 数据处理与训练入口 | 训练数据和训练硬件 |
| 第三方许可说明 | 外部资源的获取及访问资格 |

权重、数据、输出、视频与机器专用 `*.local.yaml` 按本地路径管理。发布项目时保留 `LICENSE` 和 `third_party/licenses/`，注明上游代码来源。

## 阅读顺序

1. `README.md`：安装、入口与约束。
2. `async_benchmark.yaml`：实验参数。
3. `split/client.py` → `protocol.py` → `server.py`：跨设备数据链路。
4. `models/turbovla.py` → `action_head.py`：模型结构。
5. `async_rollout.py::ActionTimeline.merge()`、`run_episode()`：时序行为。
6. `benchmark_async.py::summarize_episodes()`：指标口径。

## 工程验证流程

按“环境预检 → 模型输出一致性 → 三模式任务对比 → 长时运行”组织验证，保存配置、设备环境与结果文件。具体命令和指标见[验证与结果](./validation.md)，网络及设备运行条件见[系统能力](./capabilities.md)。
