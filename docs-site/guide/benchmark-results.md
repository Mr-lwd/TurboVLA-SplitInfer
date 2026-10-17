# Measured results

Results come from completed runs. Tables and figures share one appendable data catalog. Async maps to the CLI name `replace`.

<BenchmarkDashboard />

## Static comparison and downloads

¹ Mean and p95 exclude the first N calls per episode; N is listed in the source table. Response latency spans a policy call through receipt of a complete action chunk. Remote calls include preprocessing, transport and server inference; values are not per-action latency. `—` means not recorded.

[Download current JSON](../../reports/evaluation/latest.json) · [Download summary CSV](../../reports/evaluation/summary.csv)

<details class="benchmark-details"><summary>Full figures and records</summary>

## LIBERO Spatial · Measured comparison

9 matched successful cases · Excluded task/episode: 4/0

| Device / mode | Matched cases | Executed steps | Total time / s | Mean response¹ / ms | Response p95¹ / ms | Control interval p95 / ms | Hold steps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 9 | 868 | 71.40 | 125.01 | 127.70 | 192.13 | 0 |
| Thor local | 9 | 898 | 26.95 | 31.15 | 33.36 | 55.83 | 0 |
| Sync | 9 | 902 | 74.76 | 134.03 | 285.30 | 167.40 | 0 |
| Async / replace | 9 | 900 | 65.72 | 113.14 | 235.42 | 82.33 | 3 |
| Blend | 9 | 893 | 65.94 | 116.92 | 226.76 | 81.35 | 0 |

![LIBERO Spatial · Measured comparison four metrics](../../assets/benchmarks/libero-spatial-common-success.svg)

- Only 9 cases successful in all 5 modes are included; excluded: task 4 / episode 0.
- Recomputed from existing records without rerunning evaluation. Cases match by task ID / episode; means and p95 use retained calls and control steps.
- Matched case counts are not overall success rates. Complete successes and failures remain in the source records.
- Response mean and p95 exclude the first call per episode. Total time includes initial inference waits; slow within-episode control intervals are retained.
- All runs use LIBERO Spatial, 10 tasks with one trial each, seed 7, BF16 and chunk size 12. Local runs have no wall-clock rate cap; remote runs are capped at 20 Hz with replanning every 4 steps, a 3-step blend window and no injected delay.
- Full runs: Orin local succeeds in 10/10 episodes over 1002 steps; Thor local succeeds in 9/10 over 1118 steps, failing task 4. Sync also fails task 4. Trajectories and step counts differ, so duration differences are not pure model speedups.
- Runs were recorded at different revisions and times. Local metadata does not include checkpoint SHA-256, so filenames alone cannot establish weight identity with remote runs.
- The recorded Orin board is Orin NX Engineering Reference Developer Kit, which differs from the project Orin Nano label. Results therefore use the generic Orin name.

### Scheduling and calls

| Mode | Calls: all / filtered | Mean first response / ms | Post-bootstrap blocking / s | Inference / env.step overlap | drain / s | Command-change L2 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Orin local | 76 / 67 | 344.75 | — | — | — | — |
| Thor local | 78 / 69 | 96.32 | — | — | — | — |
| Sync | 78 / 69 | 169.40 | 9.295 | 0.00 | 0.005 | 0.199 |
| Async / replace | 224 / 215 | 117.50 | 0.000 | 94.14 | 0.012 | 0.211 |
| Blend | 226 / 217 | 135.29 | 0.000 | 93.74 | 0.076 | 0.199 |

Overlap is a percentage. L2 measures adjacent six-dimensional relative commands with mixed translation/rotation units; it is not physical jerk.

### Latency breakdown

![Complete local calls and remote latency stages](../../assets/benchmarks/libero-spatial-common-success-stages.svg)

[Download SVG](../../assets/benchmarks/libero-spatial-common-success-stages.svg) · [Download PNG](../../assets/benchmarks/libero-spatial-common-success-stages.png)

Local bars show complete calls. Remote stages use the same filtered samples and their means sum to mean response latency. p95 is computed separately. See [Data maintenance](./benchmark-data.md)。

| Remote mode | Orin preprocessing | Encoding | Thor decode/queue | Thor inference | HTTP/transport | Other overhead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sync | 6.99 | 6.87 | 2.72 | 28.81 | 88.41 | 0.24 |
| Async / replace | 11.02 | 7.46 | 2.68 | 27.93 | 63.74 | 0.32 |
| Blend | 10.35 | 7.28 | 2.68 | 27.95 | 68.36 | 0.31 |

Units: ms. HTTP/transport includes receive waits and system overhead. No breakdown is inferred from incomplete or mismatched samples.

### Source runs

| Source run | Configuration | Initial calls excluded / episode |
| --- | --- | ---: |
| Orin Remote inference | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| Orin local | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |
| Thor local | libero_spatial / bf16 / seed 7 / chunk 12 | 1 |

### Per-task results

| Mode | task ID | episode | Success | Steps | Task time / s | Hold steps |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| Orin local | 0 | 0 | Yes | 76 | 7.81 | 0 |
| Orin local | 1 | 0 | Yes | 111 | 8.52 | 0 |
| Orin local | 2 | 0 | Yes | 90 | 7.04 | 0 |
| Orin local | 3 | 0 | Yes | 80 | 6.18 | 0 |
| Orin local | 5 | 0 | Yes | 95 | 7.69 | 0 |
| Orin local | 6 | 0 | Yes | 100 | 8.24 | 0 |
| Orin local | 7 | 0 | Yes | 107 | 9.13 | 0 |
| Orin local | 8 | 0 | Yes | 96 | 7.47 | 0 |
| Orin local | 9 | 0 | Yes | 113 | 9.33 | 0 |
| Thor local | 0 | 0 | Yes | 79 | 2.62 | 0 |
| Thor local | 1 | 0 | Yes | 118 | 3.40 | 0 |
| Thor local | 2 | 0 | Yes | 95 | 2.54 | 0 |
| Thor local | 3 | 0 | Yes | 87 | 2.51 | 0 |
| Thor local | 5 | 0 | Yes | 93 | 2.85 | 0 |
| Thor local | 6 | 0 | Yes | 105 | 3.32 | 0 |
| Thor local | 7 | 0 | Yes | 113 | 3.50 | 0 |
| Thor local | 8 | 0 | Yes | 94 | 2.66 | 0 |
| Thor local | 9 | 0 | Yes | 114 | 3.56 | 0 |
| Sync | 0 | 0 | Yes | 80 | 6.30 | 0 |
| Sync | 1 | 0 | Yes | 114 | 8.90 | 0 |
| Sync | 2 | 0 | Yes | 96 | 7.78 | 0 |
| Sync | 3 | 0 | Yes | 86 | 7.53 | 0 |
| Sync | 5 | 0 | Yes | 96 | 7.77 | 0 |
| Sync | 6 | 0 | Yes | 108 | 9.15 | 0 |
| Sync | 7 | 0 | Yes | 112 | 9.74 | 0 |
| Sync | 8 | 0 | Yes | 94 | 7.22 | 0 |
| Sync | 9 | 0 | Yes | 116 | 10.37 | 0 |
| Async / replace | 0 | 0 | Yes | 79 | 5.43 | 0 |
| Async / replace | 1 | 0 | Yes | 113 | 8.18 | 0 |
| Async / replace | 2 | 0 | Yes | 99 | 7.04 | 0 |
| Async / replace | 3 | 0 | Yes | 90 | 6.51 | 0 |
| Async / replace | 5 | 0 | Yes | 90 | 6.56 | 0 |
| Async / replace | 6 | 0 | Yes | 104 | 8.05 | 0 |
| Async / replace | 7 | 0 | Yes | 112 | 8.43 | 3 |
| Async / replace | 8 | 0 | Yes | 104 | 7.30 | 0 |
| Async / replace | 9 | 0 | Yes | 109 | 8.21 | 0 |
| Blend | 0 | 0 | Yes | 82 | 5.98 | 0 |
| Blend | 1 | 0 | Yes | 107 | 7.54 | 0 |
| Blend | 2 | 0 | Yes | 97 | 6.71 | 0 |
| Blend | 3 | 0 | Yes | 88 | 6.43 | 0 |
| Blend | 5 | 0 | Yes | 94 | 7.09 | 0 |
| Blend | 6 | 0 | Yes | 105 | 7.95 | 0 |
| Blend | 7 | 0 | Yes | 113 | 8.93 | 0 |
| Blend | 8 | 0 | Yes | 96 | 6.74 | 0 |
| Blend | 9 | 0 | Yes | 111 | 8.57 | 0 |

</details>

## Methodology and updates

See [data maintenance](./benchmark-data.md). Pages and downloads publish only the current comparison, including per-task results. JSON retains source run IDs and checksums; rebuilding the website does not require raw files.
