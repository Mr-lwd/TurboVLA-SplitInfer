# Device deployment

Validate in this order: Thor service → Orin preflight → one task → multiple tasks. Run inference commands from the repository root in a Jetson Linux terminal.

## Environment

Use Python 3.10 and NVIDIA PyTorch/torchvision builds matching each device's JetPack and CUDA versions. Follow [NVIDIA's installation instructions](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html); x86_64 CUDA wheels are not interchangeable with Jetson builds.

```bash
conda create -n turbovla-libero python=3.10 -y
conda activate turbovla-libero
# Install the device-compatible torch / torchvision builds first.
python -m pip install -e '.[libero,split]' PyYAML
python -m pip check
```

Remote Orin does not load model weights, but still uses PyTorch for CPU tensor processing. The current `libero` extra also includes training-data dependencies.

## Resources

| Device | Required resources |
| --- | --- |
| Thor | TurboVLA LIBERO checkpoint, DINOv3 ViT-B, BERT base uncased and statistics JSON |
| Orin | LIBERO code, BDDL, initial states and assets; no model weights in remote mode |
| Both | Project code, dependencies, network connectivity, matching precision and chunk_size |

Models: [TurboVLA](https://huggingface.co/H-EmbodVis/TurboVLA), [DINOv3](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m), [BERT](https://huggingface.co/google-bert/bert-base-uncased). Evaluation with a complete checkpoint does not need separate GroundingDINO initialization weights.

Install LIBERO on Orin; skip cloning if it already exists:

```bash
git clone https://github.com/Lifelong-Robot-Learning/LIBERO.git ../LIBERO
python -m pip install -e ../LIBERO
```

LIBERO's older NumPy/Transformers pins differ from this project's requirements. Follow the root `pyproject.toml` and the compatible device environment.

## Start Thor

Replace the IP address and model paths. The supplied `192.168.123.38` is a configuration example.

```bash
export TURBOVLA_PYTHON="$(command -v python)"
export THOR_HOST=192.168.123.38
export DINOV3_PATH=/path/to/DINOv3
export BERT_PATH=/path/to/bert-base-uncased
bash scripts/libero/serve_thor.sh \
  --ckpt_path /path/to/turbovla_libero.pth
```

Wait for `READY`; startup loads and warms up the model. The wrapper uses `THOR_HOST` for binding. Invoking the Python module directly defaults to `127.0.0.1`.

## Check Orin

```bash
export THOR_URL=http://192.168.123.38:8765
export LIBERO_ROOT=/path/to/LIBERO
curl "$THOR_URL/health"
bash scripts/libero/run_async_benchmark.sh --preflight
```

Preflight validates configuration, paths and service metadata. It does not create a simulation or run predictions, so follow it with a single-task trial.

## Compare scheduling modes

```bash
# Same task, initial state and seed; mode order is randomized.
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes sync replace blend

# Extend the task set and repeat each task.
bash scripts/libero/run_async_benchmark.sh --task_ids 0,1,2 --num_trials_per_task 5
```

Results are written under `outputs/evaluation/async/`. Check metadata `status` and the comparison first, then inspect per-mode records and videos.

## Local baseline

```bash
bash scripts/libero/run_local_benchmark.sh --print_command
bash scripts/libero/run_local_benchmark.sh --task_ids 0
```

The local baseline runs the complete model on the current device. Set model and resource paths in `local_benchmark.yaml`; assess memory feasibility against the actual workload and device measurements.
