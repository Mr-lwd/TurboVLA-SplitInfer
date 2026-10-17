# Code coverage

The repository covers configuration, serving, client requests, scheduling, execution, reporting and tests, with entry points and validation methods for each stage.

## Code map

```text
turbovla/
  models/       TurboVLA: DINOv3, BERT, bidirectional interaction, ACT
  split/        Orin client, Thor HTTP service, versioned tensor protocol
  evaluation/   Policy adapters, action conversion, three-mode scheduling
  data/         LIBERO RLDS, mixed suites, normalization statistics
  training/     Training entry points, optimizers and EMA
scripts/libero/ Benchmarks, preflight, transport tests, parity and reporting
experiments/    LIBERO / RoboTwin entry points and configuration
tests/          Protocol, scheduling, evaluation and reporting tests
third_party/    Compatibility runtimes and retained licenses
docs-site/      Documentation source and static build configuration
assets/         Architecture diagrams, animations and deployment photographs
```

## From implementation to evidence

| Capability | Entry point / implementation | Configuration or resources | Evidence |
| --- | --- | --- | --- |
| Thor service | `serve_thor.sh` → `split/server.py` | Checkpoint, DINOv3, BERT, statistics | `/health`, service logs, split tests |
| Orin requests | `split/client.py` | URL, precision, codec | HTTP fake-policy round trips |
| Transport | `split/protocol.py` | Fixed shapes, protocol version | Bit fidelity, truncation, trailing data and non-finite-value tests |
| Three-mode evaluation | `benchmark_async.py` → `async_rollout.py` | `async_benchmark.yaml` | Alignment, blending, failure propagation and comparisons |
| Local baseline | `benchmark_local.py` | `local_benchmark.yaml` | Entry-point and statistics tests |
| Output parity | `check_split_parity.py` | Matching checkpoint and statistics | Direct/HTTP comparison on Thor and parity JSON |
| Transport selection | `benchmark_transport.py` | Fixed observations in NPZ | Codec comparison with identical returned actions |
| Training and data | `training/`, `data/` | RLDS/TFDS, statistics, initialization | Processing tools, recipes and training entry points |
| RoboTwin extension | `experiments/robotwin/` | Separate all50 configuration and external RoboTwin | Independent training/evaluation workflow |

## Resource checklist

| Provided in the repository | Prepared separately |
| --- | --- |
| Model, adapter, server, client and scheduler code | Model weights and local model directories |
| YAML/JSON configuration and LIBERO statistics | LIBERO code, BDDL, initial states and assets |
| Tests and report generators | JetPack, GPU drivers and compatible PyTorch |
| Training and data-processing entry points | Training data and compute |
| Third-party license notices | Access permissions for external resources |

Keep machine-specific settings in ignored `*.local.yaml` files. Preserve `LICENSE`, `third_party/licenses/` and upstream attribution when redistributing the project. Published evaluation artifacts remain under `outputs/` with their source records.

## Reading order

1. `README.md`: installation, entry points and operating constraints.
2. `async_benchmark.yaml`: experiment settings.
3. `split/client.py` → `protocol.py` → `server.py`: cross-device data flow.
4. `models/turbovla.py` → `action_head.py`: model architecture.
5. `async_rollout.py::ActionTimeline.merge()` and `run_episode()`: scheduling behavior.
6. `benchmark_async.py::summarize_episodes()`: metric definitions.

## Engineering validation

Proceed from preflight to model parity, three-mode task comparisons and sustained operation. Save configuration, device environment and results. See [validation](./validation.md) for commands and [system capabilities](./capabilities.md) for operating conditions.
