# Validation and results

Validate code behavior, numerical model parity and device-level task performance separately. These correspond to unit tests, inference-path comparisons and hardware evaluations.

The [benchmark explorer](./benchmark-results.md) includes Orin/Thor local baselines and Sync/Async/Blend, with per-task records and source provenance. See [data maintenance](./benchmark-data.md) to publish new runs.

## Code behavior

Run the existing tests from the repository root:

```bash
PYTHONPATH=third_party/vla_adapter:. python -m unittest discover -s tests -v
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = 'third_party/vla_adapter;.'
python -m unittest discover -s tests -v
```

Tests use mock/fake policies and local HTTP to exercise protocol, scheduling and reporting behavior.

| Test file | Coverage |
| --- | --- |
| `test_split_inference.py` | BF16/FP32 bit fidelity, codecs, HTTP round trips, connection reuse, server changes and malformed payloads |
| `test_async_inference.py` | Replacement alignment, blend weights, stale chunks, snapshots, one in-flight request, hold and worker drain |
| `test_async_benchmark.py` | Three-mode entry point, CLI overrides, preflight, failure status and reports |
| `test_local_benchmark.py` | Local configuration, call/control statistics, timestamp validation, step export and naming |
| `test_legacy_split_reports.py` | Legacy report reconstruction and missing metrics |
| `test_libero_video_timing.py` | Real waits, terminal frames and playback timing |
| `test_benchmark_report.py` | Imports, source checks, published control intervals, source preservation and stage accounting |

## Numerical model parity

With Thor serving the model, compare direct inference and HTTP on the same device:

```bash
python scripts/libero/check_split_parity.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --ckpt_path /path/to/turbovla_libero.pth \
  --dinov3_path /path/to/DINOv3 \
  --bert_path /path/to/bert-base-uncased
```

The script checks the checkpoint SHA-256 and, by default, compares three BF16 input batches with `rtol=0, atol=1e-6`.

## Fixed-observation transport test

Prepare an NPZ containing `primary` and `wrist` as uint8 `[N,256,256,3]`, `state` as float32 `[N,8]`, and `instruction` as strings `[N]`.

```bash
python scripts/libero/benchmark_transport.py \
  --remote_policy_url http://192.168.123.38:8765 \
  --observations /path/to/observations.npz \
  --repetitions 30 --warmup 3
```

The script compares compression and keep-alive while requiring identical actions for the same observations. It measures the request/inference pipeline; task success requires complete rollouts.

## Result files

Local runs are stored in `outputs/evaluation/local/<device>_<suite>_<precision>_<timestamp>/`. The raw JSON includes episode `step_timings`; `_summary.json` includes control-interval mean, median, p95, minimum and maximum. The call CSV and `_steps.csv` retain per-call and per-action details. The first action in each episode has no preceding interval. Missing legacy timestamps cannot be reconstructed from mean inference latency.

Remote runs are stored in `outputs/evaluation/async/<device_pair>_<suite>_<timestamp>/`, with per-mode files at the run root and videos under `<mode>/videos/`.

| Suffix | Contents |
| --- | --- |
| `_metadata.json` | Resolved configuration, software/hardware, model hash, run order and completed/failed status |
| `_<mode>.json` | Raw episodes, actions, control steps, requests and waits |
| `_<mode>_summary.json` | Per-mode statistics |
| `_<mode>_calls.csv` / `_steps.csv` | Request and control-step details |
| `_comparison.json` / `.csv` | Mode comparisons; a failed run is not a complete comparison |
| `*_realtime.mp4` | Wall-clock playback retaining waits, background inference and hold |

## Metric definitions

| Metric | Meaning and scope |
| --- | --- |
| `success_rate` | Successful episodes / all episodes; report task count and repetitions |
| `control_intervals.p95_ms` | p95 of consecutive action-start gaps within episodes, pooled across retained episodes; independent of initial-call filtering |
| `hold_steps` | Steps with no available action; interpret alongside success and buffer exhaustion |
| `round_trip_s` | Request round trip including server processing, not network-only latency |
| `transport_overhead_s` | Round trip minus server total; still includes HTTP, socket and response-processing overhead |
| `filtered_calls` | Calls after excluding the configured initial calls per episode; raw samples remain available |
| `server_cuda_peak_*` | Allocator peak over the service lifetime, including model loading, warmup and earlier requests |
| `worker_drain_after_episode_s` | Time waiting for the worker after rollout completion, reported separately |

Remote control is capped at 20 Hz; the local baseline has no wall-clock rate cap. A lower control-interval p95 means fewer long update gaps, not necessarily smoother motion. Inspect interval variability, hold steps and action changes together.

Stage timers can be nested and must not all be added. In asynchronous modes, inference overlaps execution, so subtracting cumulative inference from wall time does not yield other overhead.

## Device evaluation

Hold checkpoint, tasks, initial states, seed and image configuration constant. Record power modes, temperature and network conditions. Increase tasks and repetitions, add latency stress tests, and report success, p95, hold steps, stale chunks and total duration together.
