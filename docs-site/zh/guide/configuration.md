# 配置速查

远程入口读取 `experiments/libero/configs/async_benchmark.yaml`。复制为 `async_benchmark.local.yaml` 可保存设备本地参数，再通过 `--config` 指定。

## 常用参数

| 位置 / 参数 | 默认 | 作用与约束 |
| --- | --- | --- |
| `evaluation.remote_policy_url` | `http://192.168.123.38:8765` | 替换为 Thor 地址；当前客户端仅接受 HTTP |
| `evaluation.remote_timeout_s` | `120.0` | 请求超时，非硬实时 deadline |
| `evaluation.remote_compression` | `auto` | 优先 zstd_shuffle → lz4_shuffle → zlib_shuffle → zlib |
| `evaluation.remote_keepalive` | `true` | 复用 TCP 连接 |
| `evaluation.precision` | `bf16` | 与服务匹配；协议还支持 fp32 |
| `evaluation.chunk_size` | `12` | split v1 LIBERO 动作块 |
| `evaluation.task_suite_name` | `libero_spatial` | 任务套件 |
| `evaluation.task_ids` | 空 | 全部任务；用 `0,1,2` 缩小范围 |
| `evaluation.num_trials_per_task` | `1` | 正式比较时应增加重复次数 |
| `evaluation.seed` | `7` | 随机种子 |
| `experiment.modes` | `[sync, replace, blend]` | 命令行不接受 `async` 别名 |
| `experiment.replan_every_steps` | `4` | 大于 0、小于 chunk_size；每隔这些控制步尝试请求 |
| `experiment.blend_steps` | `3` | 大于 0、不超过 chunk_size |
| `experiment.control_hz` | `20.0` | 墙钟频率上限，不保证实际达到 |
| `experiment.extra_delay_s` | `0.0` | 每次调用额外延迟，供压力实验 |
| `benchmark.exclude_first_calls` | `1` | 每 episode 排除首调用，仅影响过滤统计 |

## 覆盖优先级

普通评测参数由命令行覆盖 YAML。`THOR_URL` 覆盖配置中的服务地址，显式 `--remote_policy_url` 再覆盖环境变量。资源路径通常按命令行、环境变量、YAML 的顺序解析。

```bash
cp experiments/libero/configs/async_benchmark.yaml \
   experiments/libero/configs/async_benchmark.local.yaml

bash scripts/libero/run_async_benchmark.sh \
  --config experiments/libero/configs/async_benchmark.local.yaml \
  --modes blend --replan_every_steps 4 --blend_steps 3
```

## 保持一致的字段

服务和客户端的 `precision`、`chunk_size` 必须一致；benchmark 还校验 `stats_key`。当前 key 为 `libero_all4_no_noops`。更换模型应重启服务并重新连接客户端，不能在同一 episode 中悄悄切换服务实例。

## 数据与图像尺寸

LIBERO split 路径要求已旋转的 256×256 RGB，两视角；不要套用 RoboTwin / StarVLA 的 224px resize。在线评测只需环境资源，不消费演示数据目录；训练才需要 RLDS / TFDS 数据。
