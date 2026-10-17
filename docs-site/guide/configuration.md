# Configuration reference

The remote benchmark reads `experiments/libero/configs/async_benchmark.yaml`. Copy it to `async_benchmark.local.yaml` for device-specific settings and select it with `--config`.

## Common parameters

| Parameter | Default | Meaning and constraint |
| --- | --- | --- |
| `evaluation.remote_policy_url` | `http://192.168.123.38:8765` | Replace with Thor's address; the client currently accepts HTTP only |
| `evaluation.remote_timeout_s` | `120.0` | Request timeout, not a hard real-time deadline |
| `evaluation.remote_compression` | `auto` | Prefers zstd_shuffle → lz4_shuffle → zlib_shuffle → zlib |
| `evaluation.remote_keepalive` | `true` | Reuses the TCP connection |
| `evaluation.precision` | `bf16` | Must match the server; fp32 is also supported |
| `evaluation.chunk_size` | `12` | LIBERO action chunk in split v1 |
| `evaluation.task_suite_name` | `libero_spatial` | Task suite |
| `evaluation.task_ids` | Empty | All tasks; use `0,1,2` for a subset |
| `evaluation.num_trials_per_task` | `1` | Increase repetitions for a broader evaluation |
| `evaluation.seed` | `7` | Random seed |
| `experiment.modes` | `[sync, replace, blend]` | The CLI does not accept `async` as an alias |
| `experiment.replan_every_steps` | `4` | Positive and below chunk_size; attempts a request at this control-step interval |
| `experiment.blend_steps` | `3` | Positive and no greater than chunk_size |
| `experiment.control_hz` | `20.0` | Wall-clock frequency limit, not a guaranteed rate |
| `experiment.extra_delay_s` | `0.0` | Added latency per call for stress experiments |
| `benchmark.exclude_first_calls` | `1` | Initial calls excluded per episode from filtered statistics only |

## Override precedence

CLI evaluation options override YAML. `THOR_URL` overrides the configured server address; an explicit `--remote_policy_url` overrides the environment variable. Resource paths generally resolve in CLI → environment → YAML order.

```bash
cp experiments/libero/configs/async_benchmark.yaml \
   experiments/libero/configs/async_benchmark.local.yaml
bash scripts/libero/run_async_benchmark.sh \
  --config experiments/libero/configs/async_benchmark.local.yaml \
  --modes blend --replan_every_steps 4 --blend_steps 3
```

## Fields that must agree

Server and client must share `precision` and `chunk_size`. The benchmark also checks `stats_key`, currently `libero_all4_no_noops`. Restart the service and reconnect when switching models; do not change server instances within an episode.

## Data and image sizes

The LIBERO split path expects two rotated 256×256 RGB views. Do not substitute the 224px RoboTwin/StarVLA preprocessing path. Online evaluation needs environment assets, not demonstration data; training requires RLDS/TFDS data.
