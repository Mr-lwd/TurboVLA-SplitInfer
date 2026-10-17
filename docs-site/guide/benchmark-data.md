# Benchmark data and methodology

The website and README show the latest comparison using device and mode names, without date labels or historical experiment selectors.

## Current comparison

Orin local, Thor local, Sync, Async/replace and Blend are compared on **nine commonly successful cases**. Match by `(task_id, episode)`: tasks **0, 1, 2, 3, 5, 6, 7, 8, 9**, all at episode 0. Thor local and Sync failed task 4, so that task is excluded from all five modes.

| Mode | Cases | Total time / s | Response mean / p95 / ms | Control-interval p95 / ms |
| --- | ---: | ---: | ---: | ---: |
| Orin local | 9 | 71.40 | 125.01 / 127.70 | 192.13 |
| Thor local | 9 | 26.95 | 31.15 / 33.36 | 55.83 |
| Sync | 9 | 74.76 | 134.03 / 285.30 | 167.40 |
| Async | 9 | 65.72 | 113.14 / 235.42 | 82.33 |
| Blend | 9 | 65.94 | 116.92 / 226.76 | 81.35 |

## Measurement scope

- Response and stage timings: select the common cases, exclude the first call per episode, then pool remaining samples for means and p95.
- Wall time, control intervals, steps, hold, blocking and overlap all use the same nine cases. Wall time retains initial inference waits.
- Matched cases support timing comparisons, not overall success claims. Full-run success counts are 10/10, 9/10, 9/10, 10/10 and 10/10 respectively.
- Local runs have no wall-clock rate cap; remote runs are capped at 20 Hz. Interpret total time alongside trajectories and action counts.
- Remote response includes Orin preprocessing/encoding, HTTP/transport, Thor decoding/queueing and inference. Stage means use matching samples and sum to mean response latency; p95 values are computed independently.
- Task time excludes model loading, environment reset, settling and video encoding. Post-episode worker drain is reported separately.
- Metrics are recomputed from existing records, without rerunning evaluation. Downloaded JSON retains device environments, checkpoint information, run IDs and source SHA-256 checksums.

## Data files

| File | Role |
| --- | --- |
| `reports/evaluation/catalog.json` | Full source catalog; `featured_group` selects the current comparison |
| `reports/evaluation/latest.json` | Current comparison and relevant source records, consumed by the website |
| `reports/evaluation/summary.csv` | Per-mode summary of the current comparison |
| `assets/benchmarks/` | Metric and latency-breakdown figures |

The generator publishes only the selected comparison. Original records remain in the catalog, without a historical selector in the website. Source run IDs and checksums remain in JSON for traceability.

## Publish new results

Run from the repository root. Figure generation uses Matplotlib and its bundled English fonts.

```bash
# Import complete runs into a common source group.
python scripts/libero/build_benchmark_report.py add /path/to/completed/run \
  --group spatial-next --title 'LIBERO Spatial'
python scripts/libero/build_benchmark_report.py add /path/to/another/run \
  --group spatial-next

# Select the intersection of successful cases.
python scripts/libero/build_benchmark_report.py select-common-success \
  --source-group spatial-next --group spatial-next-common-success --featured

# Regenerate JSON, CSV, figures, README and the data page.
python scripts/libero/build_benchmark_report.py build
```

Selection validates tasks, seeds, raw files and checksums; it does not start model evaluation. Do not manually edit numeric metrics or generated sections. Once the catalog exists, `build` can regenerate publication without raw `outputs/` or GPU inference.

```bash
cd docs-site
npm ci
npm run check
npm run build
```
