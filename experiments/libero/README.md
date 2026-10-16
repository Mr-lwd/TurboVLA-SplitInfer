# LIBERO

This directory contains the released LIBERO recipe and public entry points for the root `turbovla` package. The configuration uses two DINOv3 views, an online BERT encoder, 7-D actions, and a chunk size of 12. The task and episode rollout protocol is the VLA-Adapter-derived implementation under `third_party/vla_adapter/`.

## Layout

```text
../../turbovla/             model, RLDS data, training, and policy code
configs/                    released mixed-suite normalization statistics
train.py                    public mixed-suite training entry point
evaluate.py                 public single-checkpoint evaluation entry point
../../scripts/libero/       data, statistics, and evaluation utilities
../../third_party/          VLA-Adapter rollout protocol and license
```

## Environment

The reference environment used PyTorch 2.3.1, torchvision 0.18.1, transformers 4.56, TensorFlow 2.20, and tensorflow-datasets 4.9.3.

```bash
pip install -e ".[libero]"
```

Install LIBERO separately. DINOv3 and GroundingDINO weights are not included.

## Data

```text
data/libero/
|-- libero_10_no_noops/1.0.0/
|-- libero_goal_no_noops/1.0.0/
|-- libero_object_no_noops/1.0.0/
`-- libero_spatial_no_noops/1.0.0/
```

The repository does not redistribute demonstrations. Use `scripts/libero/regenerate_libero_no_noops.py` with the official LIBERO data, then convert the derived trajectories to TFDS/RLDS. Released normalization statistics are in `experiments/libero/configs/libero_all4_stats.json`.

## Training

The released recipe uses full DINOv3 ViT-B unfreezing, global batch 128 on four GPUs (per-device batch size 8 with 4 gradient-accumulation steps), 40k optimizer steps, 10k warmup steps, learning rate `5e-5`, seed 42, FP32 policy parameters, and BF16 autocast for DINOv3.

```bash
torchrun --nproc_per_node=4 experiments/libero/train.py \
  --dataset_dir data/libero/libero_10_no_noops/1.0.0 \
  --dataset_dirs "data/libero/libero_10_no_noops/1.0.0,data/libero/libero_goal_no_noops/1.0.0,data/libero/libero_object_no_noops/1.0.0,data/libero/libero_spatial_no_noops/1.0.0" \
  --stats_path experiments/libero/configs/libero_all4_stats.json \
  --stats_key libero_all4_no_noops \
  --dinov3_path facebook/dinov3-vitb16-pretrain-lvd1689m \
  --bert_path google-bert/bert-base-uncased \
  --allow_hf_download \
  --pretrained_init_ckpt /path/to/groundingdino_swint_ogc.pth \
  --batch_size 8 \
  --checkpoint_dir outputs/checkpoints
```

## Evaluation

### Orin / Thor 本机推理耗时评测

在各设备上激活自己的 Python 环境，然后执行同一条命令：

```bash
# Orin: conda activate turbovla-libero
# Thor: conda activate turbovla
bash scripts/libero/run_local_benchmark.sh
```

默认沿用 `libero_spatial`、每任务 1 次、seed 7、BF16、chunk/open-loop 12、
EGL，并保存普通回放和带真实等待时间的回放。所有模型推理均在当前设备执行。
脚本检查 CUDA/BF16 支持，不会静默切换精度。它使用当前环境的 `python`，也可通过
`TURBOVLA_PYTHON=/path/to/python` 指定。比较两台设备时应使用相同权重、参数及任务，
停止其他推理负载，保持功耗模式和散热条件一致；脚本不会停止服务或修改功耗模式。

路径和评测参数统一在 [`configs/local_benchmark.yaml`](configs/local_benchmark.yaml) 修改，无需编辑 Python：

- `paths`：checkpoint、LIBERO 代码目录、DINOv3、BERT、统计文件；支持单一路径或候选路径列表。
- `libero_paths`：演示数据 `datasets`、BDDL、初始状态、assets 和 benchmark 根目录。
- `benchmark`：输出根目录和每个 episode 排除的首次调用数。
- `evaluation`：套件、任务 ID、次数、seed、精度、chunk、图像大小、视频开关等原评测参数。

所有相对路径（包括 `--config`）均相对于仓库根目录，支持 `~`、`${REPO_ROOT}` 和环境变量。
`libero_paths` 还支持 `${libero_root}`，引用最终选中的 LIBERO 目录。
默认模型路径列表依次查找 `../models`、`~/models`、仓库内 `models`，可直接改为自己的绝对路径。
路径优先级为 **CLI > 环境变量 > YAML**，支持的环境变量是 `CKPT_PATH`、`LIBERO_ROOT`、
`DINOV3_PATH`、`BERT_PATH`、`STATS_PATH`；非路径参数为 **CLI > YAML > 原评测器默认值**。
YAML 中的参数名称和类型会被检查，`task_ids` 应写为字符串，例如 `"0,1"`。

每次运行在输出目录生成 `libero_config/config.yaml`，通过 `LIBERO_CONFIG_PATH` 供本次评测读取，
不修改或读取全局 `~/.libero/config.yaml`。数据集、BDDL、初始状态和 assets 均以此处配置为准。
在线 rollout 不读取演示数据，因此 `datasets` 允许尚不存在，其余 LIBERO 资源目录会检查存在性。
也可使用 `--libero_datasets /path/to/data`、`--libero_bddl_files ...`、`--libero_init_states ...`、
`--libero_assets ...`、`--libero_benchmark_root ...` 临时覆盖对应路径。

```bash
# 可选：复制一份本机配置，修改路径和参数（*.local.yaml 不提交到 Git）
cp experiments/libero/configs/local_benchmark.yaml experiments/libero/configs/orin.local.yaml
bash scripts/libero/run_local_benchmark.sh --config experiments/libero/configs/orin.local.yaml
```

自定义配置文件应保留四个配置区块及路径字段；`evaluation` 可增减参数。
元数据会保存配置文件内容、最终评测参数和 LIBERO 资源路径，方便复现。

```bash
# 只检查设备、路径并打印评测命令，不加载权重
bash scripts/libero/run_local_benchmark.sh --print_command
# 单任务冒烟测试
bash scripts/libero/run_local_benchmark.sh --task_ids 0 --save_video false
# 修改套件、重复次数、输出根目录
bash scripts/libero/run_local_benchmark.sh \
  --task_suite_name libero_object --num_trials_per_task 3 \
  --output_root outputs/evaluation/local
```

自动根据 GPU / Jetson 板卡名称识别 `orin` 或 `thor`，未识别设备使用清理后的 GPU 名称。
每次创建独立目录，例如：
`outputs/evaluation/local/orin_libero_spatial_bf16_<时间戳>/`。
JSON、CSV、日志文件的文件名均包含设备、套件、精度和时间戳；视频保存在该目录的
`orin_videos/` 或 `thor_videos/` 下，内部保留任务/episode 文件名。生成数据被 Git 忽略。

- `*_summary.json`：所有调用、每个 episode 首次调用、过滤后调用的 count/mean/median/p95/min/max，
  成功率、完整 rollout 时间、推理总时间、非推理时间及吞吐量。
- `*.csv`：每次调用的任务、episode、step、秒/毫秒耗时及是否计入过滤统计。
- `*.json`（无额外后缀）：原始评测结果，包含逐 episode 耗时、逐次调用及视频路径。
- `*_metadata.json`：GPU、板卡、软件版本、Git 状态、完整配置、运行状态、功耗模式（可读取时）、
  PyTorch CUDA 分配器峰值内存和包含加载/视频导出等开销的总时间。峰值内存不等于 Jetson 总共享内存。
- `*.log`：评测器日志；异常时 metadata 标为 failed，不生成成功汇总。

一次调用预测一个 chunk，默认 12 个 action。耗时包含预处理、神经网络、CPU/GPU 传输和
动作解码，返回 CPU NumPy 动作意味着本次 GPU 工作已完成；这是完整 policy 调用耗时，
不是纯 GPU kernel 时间。图像旋转在调用计时之外。
默认额外统计“排除每个 episode 第一次调用”的分布，可通过 `--exclude_first_calls 0` 保留全部。
这只是事后筛选，不进行额外 warmup，也不保证筛选后的调用已达到稳态，原始数据始终保留。
`filtered_amortized_ms_per_predicted_action` 是 chunk 延迟除以模型 chunk 大小，
不表示每隔这么多毫秒就有一个动作返回。实际执行步数可能因提前成功而少于预测动作数。
rollout 时间不包含模型加载、reset、settling 或视频编码；非推理差值也包含图像处理和 Python 开销。

For Orin preprocessing with neural inference on a remote Jetson Thor and actions returned to Orin, see [the split inference guide](SPLIT_INFERENCE.md). The evaluator supports `--remote_policy_url http://192.168.123.38:8765` and saves network/server timing alongside both replay videos.

`bash scripts/libero/run_split_orin.sh` now uses `configs/split_benchmark.yaml` and automatically
exports the same summary/CSV/metadata format as the local benchmark, plus per-stage remote
statistics. Existing split JSON files can be summarized without rerunning inference with
`python scripts/libero/summarize_split.py <result.json> --client_device orin`.

For an isolated comparison of synchronous execution, background prediction with aligned action
replacement, and short-window action blending, see [the async experiment guide](ASYNC_INFERENCE.md).
Run `bash scripts/libero/run_async_benchmark.sh`; settings live in `configs/async_benchmark.yaml`.
This experiment leaves the normal evaluator and pretrained model unchanged.

One invocation evaluates one checkpoint on one suite. Checkpoint selection and multi-GPU scheduling are intentionally outside the evaluator.

```bash
python experiments/libero/evaluate.py \
  --ckpt_path pretrained/TurboVLA/checkpoints/libero/turbovla_libero.pth \
  --dinov3_path /path/to/dinov3-vitb \
  --bert_path /path/to/bert-base-uncased \
  --stats_path experiments/libero/configs/libero_all4_stats.json \
  --stats_key libero_all4_no_noops \
  --task_suite_name libero_object \
  --num_trials_per_task 50 \
  --chunk_size 12 \
  --num_open_loop_steps 12 \
  --seed 7 \
  --precision bf16 \
  --result_json_path outputs/evaluation/object.json
```


Use `--dry_run_model_load true` to validate checkpoint compatibility without a simulator rollout. Complete release checkpoints contain BERT, DINOv3, the vision-language interaction module, and the action head in one strict-loadable state dict. `configs/online_text_layout.json` stores tokenizer padding metadata for the 40 standard instructions; it contains no embeddings or cached model outputs.

With `--save_video true`, each episode produces two 20 FPS videos:

- `task00_ep000_success.mp4`: the original replay, one frame per control step, omitting computation delays.
- `task00_ep000_success_realtime.mp4`: a wall-clock replay that holds each observation for its measured duration and labels inference waits. Timing starts after the settling steps and ends after the final action. It includes preprocessing, inference, transfers, and environment stepping, but excludes model loading, environment reset, settling, and video encoding. The final observation is shown for one additional frame; duration differs from the measured time by at most 0.1 seconds.

The result JSON includes per-episode wall time, video durations, and each action chunk's inference timing. Inference time includes preprocessing and CPU/GPU transfers until CPU actions are available. The simulator pauses while synchronous inference runs; the timed video reproduces that pause and does not model a physical robot moving during inference. Use `--save_realtime_video false` to save only the original replay. Videos recorded before timing was added cannot recover their original delays.

The rollout protocol is derived from [VLA-Adapter](https://github.com/OpenHelix-Team/VLA-Adapter/commit/23fa0c9c159e2aa04341cdd3e924f44061311060). See `third_party/licenses/VLA-Adapter.txt` for the retained license and attribution.
