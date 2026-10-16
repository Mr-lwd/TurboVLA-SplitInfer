# Orin → Thor → Orin 双设备推理

Orin 从 LIBERO 双路相机获取连续画面，完成图像与机器人状态的预处理，把模型输入发给 Thor。Thor 运行 TurboVLA，返回 12 步、每步 7 维的动作。Orin 根据同步、异步替换或异步融合模式调度动作和新观测，形成闭环。这对应“端侧初步计算 → 网络传输 → 边缘神经网络分析 → 返回结果”的两设备结构。

```mermaid
flowchart LR
    subgraph A[Jetson Orin / 192.168.123.141]
        Camera[LIBERO 两路 RGB 画面 + 状态]
        Pre[画面旋转 / RGB 归一化\n状态归一化 / bf16 / 无损压缩]
        Control[调度动作缓冲区\n保存视频与耗时]
        Camera --> Pre
        Control --> Camera
    end
    subgraph B[Jetson Thor 128 GB / 192.168.123.38]
        Receive[解压 / 张量校验]
        Model[DINOv3 + BERT\n视觉语言融合 + 动作头]
        Action[动作反归一化 / 返回 12×7 数组]
        Receive --> Model --> Action
    end
    Pre -->|HTTP 张量请求| Receive
    Action -->|动作 + 服务端计时| Control
```

## 分工与切分位置

| Orin | Thor |
| --- | --- |
| LIBERO 仿真、两路画面采集、180° 旋转 | 加载完整 TurboVLA checkpoint |
| 256×256 RGB 校验、DINOv3 输入归一化 | DINOv3、BERT、融合层、动作头的全部神经网络计算 |
| 8 维状态提取与归一化 | 将归一化动作转换为环境动作 |
| 转换至模型精度、无损压缩、发送请求 | 解压与有限值校验、GPU 推理、返回动作 |
| 执行返回动作、输出两份视频和 JSON | 输出可按 request_id 对齐的请求日志 |

这里切在神经网络之前；Orin 不加载 BERT/DINOv3/TurboVLA 权重。图像仍需满足 LIBERO 训练约定：两路、256×256、RGB、正确朝向。随机摄像头视频缺少机器人状态与对应训练场景，不能直接作为 LIBERO 策略控制输入。

预处理配置、状态统计量、模型精度和 checkpoint SHA-256 通过 `/health` 从 Thor 获取。这样两端不会因为统计文件或归一化参数不同而改变动作。BF16 以原始 16 位比特传输，FP32 以 32 位比特传输，使用协商后的无损压缩，不使用 JPEG 或 pickle。

## 传输加速（保留 Orin 端处理）

Orin 仍然执行图像方向校正、图像/状态归一化、精度转换、输入校验与压缩；Thor 还原相同张量并运行神经网络。
新版服务启用 HTTP/1.1 长连接和 TCP_NODELAY，客户端复用连接，减少重复建连及小数据包等待。
连接故障会报错，不自动重发推理请求；旧 HTTP/1.0 服务仍可连接，但无法获得长连接收益。

在两台设备各自激活的 Python 环境安装快速压缩依赖：

```bash
python -m pip install 'lz4>=4.3,<5' 'zstandard>=0.22,<1'
```

也可在安装项目时选用 `pip install -e '.[split]'`。两端同步源码并重启 Thor 服务后，配置：

```yaml
evaluation:
  remote_keepalive: true
  remote_compression: auto
```

`auto` 根据两端能力依次选择 `zstd_shuffle`、`lz4_shuffle`、`zlib_shuffle`、`zlib`，这是能力协商，不是在线测速选优。
也可显式选择 `lz4` 或 `zstd`。`*_shuffle` 在压缩前将张量元素的各字节分组，解压后逆变换；
它不改动任何浮点位，也不改变预处理切分位置。LZ4 和 Zstandard 的速度/压缩率依赖数据，最终应比较完整调用耗时。
未安装可选压缩库会选择双方支持的 zlib 方案；旧服务只选择原有 `zlib`。显式指定不支持的方案会在预检查时报错。

```bash
# 使用协商后的快速模式
bash scripts/libero/run_async_benchmark.sh --modes sync
# 同一新版服务上的 zlib / 短连接对照
bash scripts/libero/run_async_benchmark.sh --modes sync --remote_compression zlib --remote_keepalive false
```

结果记录实际 `compression` 和逐次 `connection_reused`。新增阶段 `client_request_send_s`
包含必要时建连、发送头和请求体；`client_response_wait_s` 直到收到响应头；
`client_response_read_s` 包含读取和解析响应。`server_receive_s` 从服务端解析请求头后开始计请求体读取，
不含接收请求头之前的时间。它们与原 round-trip/transport 指标存在包含关系，不能简单相加。

可用固定观测进行交错顺序的对照，避免不同闭环轨迹影响性能比较：

```bash
python scripts/libero/benchmark_transport.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --observations outputs/evaluation/transport/libero_spatial_initial_observations.npz \
  --repetitions 60 --warmup 3
```

观测 NPZ 需包含 `primary`、`wrist`（`uint8 [N,256,256,3]`，已校正方向）、
`state`（`float32 [N,8]`，未归一化）、`instruction`（字符串数组 `[N]`），不允许 pickle。
它不由上面的命令自动生成，可通过 LIBERO 初始状态采样保存。
脚本比较短连接 zlib，以及长连接的 zlib、LZ4、Zstandard 和它们各自的字节重排版本，缺少依赖的方案会注明跳过。
每组使用相同观测，要求动作数组完全一致；预热不计入测量，按固定种子交错测试顺序。
`--baseline_url` 可加入另一个旧服务端对照，要求相同权重哈希和 stats key。
输出到带设备名和时间戳的 `outputs/evaluation/transport/*.json`，包括原始样本、分阶段分布和输入文件哈希。
这是固定输入的策略调用测试，不能替代完整任务成功率验证；所有对照使用当前客户端实现。

## 启动 Thor

```bash
cd /home/jetson/LWD/TurboVLA
bash scripts/libero/serve_thor.sh
```

默认使用 `/home/jetson/anaconda3/envs/turbovla/bin/python`，本地 checkpoint、`/home/jetson/models/DINOv3` 和 `/home/jetson/models/bert-base-uncased`。出现 `READY http://192.168.123.38:8765` 后可接收请求。端口已占用时不要重复启动同一服务。

需要后台运行时：

```bash
cd /home/jetson/LWD/TurboVLA
mkdir -p outputs/split
nohup bash scripts/libero/serve_thor.sh > outputs/split/thor_server.log 2>&1 < /dev/null &
echo $! > outputs/split/thor_server.pid
```

停止该后台进程：`kill "$(cat outputs/split/thor_server.pid)"`。前台运行时按 Ctrl+C。代码更新后需要停止旧进程再启动，正在运行的客户端若检测到服务实例变化会报错，需重新运行评估。

可用 `TURBOVLA_PYTHON`、`DINOV3_PATH`、`BERT_PATH`、`THOR_HOST`、`THOR_PORT` 覆盖路径和监听地址；脚本最后的命令行参数也会透传。

## 启动 Orin

```bash
cd /home/nano1/Desktop/lwd/VLA/TurboVLA
# 运行 YAML 中配置的模式，默认 sync / replace / blend
bash scripts/libero/run_async_benchmark.sh
# 只运行原来的同步 split 基线
bash scripts/libero/run_async_benchmark.sh --modes sync
# 单任务、不生成视频
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --save_video false
# 检查路径、设备和 Thor /health，不执行推理
bash scripts/libero/run_async_benchmark.sh --preflight
```

默认 `libero_spatial` 全部任务，每任务每模式 1 回合。Orin 只需现有的
`turbovla-libero` 环境和 LIBERO 资产，无需本地 checkpoint、DINOv3 或 BERT。
唯一远程评测配置为 [`configs/async_benchmark.yaml`](configs/async_benchmark.yaml)，
包含 LIBERO 路径、Thor 地址、评测参数和调度策略。修改配置或使用 CLI 覆盖即可。
`THOR_URL`、`LIBERO_ROOT` 可覆盖对应 YAML 字段；输出用 `--output_root`，
脚本解释器用 `TURBOVLA_PYTHON` 指定。

结果写入 `outputs/evaluation/async/<客户端>_to_<服务端>_async_<套件>_<时间戳>/`，
每个模式各有 summary、原始 JSON、请求 CSV、控制步 CSV 和两类视频，
另有整体 comparison 和 metadata。同步模式也使用这一格式，便于三模式直接比较。
详细调度机制、字段、配置和示例见 [统一评测说明](ASYNC_INFERENCE.md)。

`benchmark.exclude_first_calls` 默认按回合排除第一次请求，仅影响过滤统计，
不会删除原始记录。所有远程阶段使用相同筛选规则，后续网络抖动仍保留。
`remote_stage_timings.<阶段>.filtered_calls` 提供平均/中位数/p95，缺失阶段为 null。
各阶段存在包含关系，不可相加。服务端显存是进程启动以来的 PyTorch 分配器峰值，
包括加载、预热和之前的请求，不是本回合峰值或 Jetson 总内存。

### 代码职责

- `run_async_benchmark.sh` / `benchmark_async.py`：统一远程评测入口。
- `async_benchmark.yaml`：独立完整配置；不再继承其他评测 YAML。
- `turbovla/evaluation/async_rollout.py`：sync / replace / blend 调度。
- `turbovla/split/`、`serve_thor.sh`：共享客户端、协议和 Thor 服务，三模式都依赖它们。
- `run_local_benchmark.sh`：Orin 或 Thor 的本机基准，继续独立保留。
- `benchmark_transport.py`、`check_split_parity.py`：固定观测传输测试和动作一致性验证。

### 补算已有 split 数据

```bash
python scripts/libero/summarize_split.py \
  outputs/evaluation/split_thor/libero_spatial.json --client_device orin
```

无需连接 Thor、加载权重或重新推理。新汇总、CSV 和溯源 metadata 写入原始文件旁的
`reports/orin_to_thor_split_<套件>_backfill_<导出时间戳>/`，原 JSON 和视频保持不变。
metadata 记录源文件 SHA-256、原有字段及导出时间；导出时间不是原评测时间。
`--client_device` 指定原始客户端名称，默认 `unknown_client`，不会误用当前导出机器名称。
历史结果未记录的软件版本、内存、完整启动配置等无法恢复，不会用当前机器状态填充。

## 如何读计时

每次调用仍生成一块 12 步动作。`inference_timings[].duration_s` 是 Orin 观察到的完整策略调用耗时；远程模式下不能把它当作纯模型计算时间。

其 `remote` 字段包含：

| 字段 | 含义 |
| --- | --- |
| `client_preprocess_s` | Orin 图像/状态归一化和精度转换 |
| `client_encode_s` | 输入校验、序列化和无损压缩 |
| `round_trip_s` | HTTP 请求发出至完整响应收到，包含 Thor 的处理时间 |
| `server_decode_s` | Thor 解压、张量重建和校验 |
| `server_queue_s` | 等待模型执行锁 |
| `server_inference_s` | 张量传入 GPU、模型前向、动作传回 CPU 和反归一化 |
| `server_total_s` | 从请求体读完到动作算完，不含 HTTP 收发和响应序列化 |
| `transport_overhead_s` | 往返减服务端总耗时；包含 HTTP、网络与响应处理，不能当作纯网络单向时延 |
| `request_bytes` | 压缩后的 HTTP 请求体字节数，不含 HTTP/TCP 头 |
| `uncompressed_tensor_bytes` | 压缩前张量字节数，bf16 下为 786448 |

两台机器都用各自的单调时钟记录时间间隔，不依赖系统时钟同步。服务启动预热 3 次，预热不在评估计时中；不同指令仍可能有额外首次调用开销。`sync` 在等待 Thor 时暂停环境；`replace` / `blend` 在后台预测期间继续执行缓冲区动作。异步的仿真步与墙钟对齐限制见统一评测说明。

HTTP 服务用于当前局域网，默认底层服务入口监听回环地址，Thor 启动脚本显式监听其局域网 IP。输入尺寸/请求体有上限，支持超时，服务按请求编号回应；断网或无效响应会结束评估，不会悄悄改为 Orin 本地推理。网络与仿真开销都可能抵消 Thor 模型计算的加速，应同时查看完整调用耗时和模型耗时。

## 验证

本地单元测试：

```bash
PYTHONPATH=third_party/vla_adapter:. python -m unittest discover -s tests -v
```

在 Thor 上检查直接推理与 HTTP 路径的一致性（先启动服务）：

```bash
cd /home/jetson/LWD/TurboVLA
/home/jetson/anaconda3/envs/turbovla/bin/python scripts/libero/check_split_parity.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --ckpt_path pretrained/TurboVLA/checkpoints/libero/turbovla_libero.pth \
  --dinov3_path /home/jetson/models/DINOv3 \
  --bert_path /home/jetson/models/bert-base-uncased
```

结果写入 `outputs/split/parity.json`，使用同一 checkpoint 检查 3 组双路画面与状态。跨 Orin/Thor 的完整链路由 Orin 评估 JSON 和 Thor 请求日志中的相同 `request_id` 验证。

## 2026-10-16 实机验收

Orin `192.168.123.141` → Thor `192.168.123.38`，`libero_spatial`、seed 7、bf16、动作块 12、每任务 1 回合：

- 10 回合全部完成，9/10 成功；任务 4 未成功，与 Thor 上原有单机基线逐任务一致。
- 97 次请求全部在 Thor 日志中找到相同的 request_id，服务端记录的客户端 IP 为 Orin 地址。
- 3 组直接推理/HTTP 路径对照的动作完全相同，最大绝对误差为 0。
- 10 份普通回放和 10 份墙钟视频均可解码，帧数与 JSON 时长一致；墙钟视频与实测执行时长的差异均不超过 0.1 秒。
- 两台设备上的 8 项单元测试均通过。Orin 启动命令未提供或加载本地神经网络权重。

| 每次动作块调用（97 次） | 平均 | 中位数 |
| --- | ---: | ---: |
| Orin 完整策略调用 | 189.61 ms | 147.65 ms |
| Orin 预处理 | 7.59 ms | 5.90 ms |
| Orin 校验/编码/压缩 | 18.01 ms | 17.58 ms |
| 请求往返（含 Thor 处理） | 163.77 ms | 122.43 ms |
| Thor 模型推理与动作转换 | 28.97 ms | 28.90 ms |
| 网络/HTTP 等剩余开销 | 131.29 ms | 89.05 ms |

平均请求体约 252 KiB；当前网络传输与 HTTP 开销是端到端时延的重要部分。以上是这次实际运行的观测值，启动预热、设备负载、指令及网络条件都会影响其他运行。

模型 SHA-256：`d031ad7be05a2f5d04afb3194ed26b0cb46083685edee7a5e145078a37d26bab`。Orin 的 `outputs/evaluation/split_thor/` 保留 `libero_spatial.json`、`thor_server.log`、`thor_local_baseline.json`、`parity.json`、`validation.json` 与视频。输出目录按仓库规则忽略，不随源码上传。

## 2026-10-16 传输优化验收

保持 Orin 端预处理、归一化、BF16 转换及无损压缩，保持原 Wi-Fi 网络，采用
`zstd_shuffle`（Zstandard level 1）和 HTTP/1.1 长连接。两端验证环境安装 LZ4 4.4.5、Zstandard 0.25.0。

固定输入对照采集了任务 0/1/2 在 seed 7、初始状态 0、10 步 settling 后的双路图像和真实机器人状态。
每种模式每个观测预热 3 次，测量 60 次，交错测试顺序；8 个模式的动作数组全部逐元素完全相同。
旧服务 + zlib 短连接平均 135.09 ms，新服务 + zstd_shuffle 长连接平均 105.21 ms，减少约 22.1%。
所有模式使用当前客户端，因此这是传输配置/服务端对照，不是原旧版客户端二进制的严格复现。

随后运行完整 libero_spatial（每任务 1 回合、BF16、chunk 12、seed 7、两种视频均开启）：

| 排除每个回合首次调用后的指标 | 优化前 21:41 运行 | 优化后 22:05 运行 |
| --- | ---: | ---: |
| 平均完整调用 | 128.98 ms | 114.64 ms |
| 中位数 | 108.67 ms | 92.66 ms |
| P95 | 258.05 ms | 224.86 ms |
| 平均编码耗时 | 17.76 ms | 5.45 ms |

两次均为 9/10 成功；逐任务成功/失败、执行步数和调用步号全部一致（1122 步、97 次请求）。
新版 97 次请求全部复用连接、使用 zstd_shuffle，并在 Thor 日志中匹配到请求编号。
20 个视频均通过帧数/时长检查。20 项单元测试通过，涵盖所有可用编码的 BF16/FP32 位一致性、
截断及多余数据拒绝、连接复用、旧服务协商与断线处理。

完整 rollout 的平均收益约 11.1%，小于固定输入对照；新运行中的传输/HTTP 剩余开销仍约 71.58 ms。
当前 Wi-Fi 的传输与抖动仍是主要限制，不能将本次收益保证为每次运行都相同。
验收使用 Thor 独立临时 worktree 和 8766 端口，结束后已关闭并清理；正式 8765 服务未替换。

实测输出（均被 Git 忽略）：

- `outputs/evaluation/transport/orin_to_thor_transport_20261016T220422_747227+0800.json`：固定输入对照。
- `outputs/evaluation/transport/libero_spatial_initial_observations.npz`：固定观测输入。
- `outputs/evaluation/transport/thor_validation_server.log`：服务端日志。
- `outputs/evaluation/split/orin_to_thor_split_libero_spatial_bf16_20261016T220508_967247+0800/`：完整评测、视频和 `optimization_validation.json`。
