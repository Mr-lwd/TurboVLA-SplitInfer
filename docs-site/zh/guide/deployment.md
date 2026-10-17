# 设备部署

先跑通“Thor 服务 → Orin preflight → 单任务 → 多任务”。下列推理命令在 Jetson 的 Linux 终端、仓库根目录执行。

## 准备环境

使用 Python 3.10 环境；分别安装匹配各自 JetPack / CUDA 的 NVIDIA PyTorch 与 torchvision，参考 [NVIDIA 官方安装说明](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html)。不要直接套用 x86_64 的 CUDA wheel。

```bash
conda create -n turbovla-libero python=3.10 -y
conda activate turbovla-libero
# 先安装当前设备适用的 torch / torchvision，再安装项目
python -m pip install -e '.[libero,split]' PyYAML
python -m pip check
```

Orin 远程模式不加载权重，但当前客户端仍依赖 PyTorch 做 CPU 张量处理，并非纯 NumPy 客户端。当前 `libero` extra 包含训练数据依赖，尚未单独拆出轻量运行安装项。

## 放置资源

| 位置 | 必需资源 |
| --- | --- |
| Thor | TurboVLA LIBERO checkpoint、DINOv3 ViT-B、BERT base uncased、统计 JSON |
| Orin | LIBERO 代码、BDDL、初始状态、assets；远程模式不需要模型权重 |
| 两端 | 项目代码、依赖、可互访网络、相同精度与 chunk_size |

模型入口：[TurboVLA](https://huggingface.co/H-EmbodVis/TurboVLA)、[DINOv3](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m)、[BERT](https://huggingface.co/google-bert/bert-base-uncased)。完整 checkpoint 评测无需另配 GroundingDINO 初始化权重。

Orin 安装 LIBERO（已有目录则跳过 clone）：

```bash
git clone https://github.com/Lifelong-Robot-Learning/LIBERO.git ../LIBERO
python -m pip install -e ../LIBERO
```

LIBERO 旧 requirements 的 NumPy / Transformers 固定版本与本项目不一致，遵循根目录 `pyproject.toml` 及配套环境约束。

## 启动 Thor

替换以下 IP 和模型路径；默认脚本中的 `192.168.123.38` 只是现有配置。

```bash
export TURBOVLA_PYTHON="$(command -v python)"
export THOR_HOST=192.168.123.38
export DINOV3_PATH=/path/to/DINOv3
export BERT_PATH=/path/to/bert-base-uncased
bash scripts/libero/serve_thor.sh \
  --ckpt_path /path/to/turbovla_libero.pth
```

看到 `READY` 后再连接。服务启动会加载权重并预热；默认监听由脚本的 `THOR_HOST` 决定。直接运行 Python 模块时默认只监听 `127.0.0.1`。

## 检查 Orin

```bash
export THOR_URL=http://192.168.123.38:8765
export LIBERO_ROOT=/path/to/LIBERO
curl "$THOR_URL/health"
bash scripts/libero/run_async_benchmark.sh --preflight
```

`--preflight` 验证配置、资源路径和服务元数据，不创建仿真、不执行模型预测；因此通过后仍须运行单任务。

## 运行对比

```bash
# 同一任务、初始状态和 seed；各模式顺序随机化
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes sync replace blend

# 扩大试验次数和任务集合
bash scripts/libero/run_async_benchmark.sh --task_ids 0,1,2 --num_trials_per_task 5
```

输出在 `outputs/evaluation/async/`。先核对 metadata 中的 `status` 和 comparison，再查看每个模式的原始记录及视频。

## 本机基线

```bash
bash scripts/libero/run_local_benchmark.sh --print_command
bash scripts/libero/run_local_benchmark.sh --task_ids 0
```

本机基线将全部模型放到当前设备，需配置 `local_benchmark.yaml` 的模型和资源路径。Orin 8GB 上能否在指定负载下运行，应由实际资源与运行结果决定。
