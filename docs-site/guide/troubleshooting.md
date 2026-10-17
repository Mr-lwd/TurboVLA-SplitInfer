# Troubleshooting

Start with run metadata and Thor logs. Change one factor at a time so that failures remain attributable.

| Symptom | Check | Action |
| --- | --- | --- |
| Connection failure / timeout | Thor READY status, IP, port, binding and network | Correct THOR_HOST / THOR_URL; retain logs before restarting |
| precision / chunk_size mismatch | Client and server metadata | Match settings; split v1 uses LIBERO 12×7 chunks |
| server instance changed | Service restart during a run | Reconnect and start a new experiment |
| stats_key mismatch | Statistics file and key | Use `libero_all4_no_noops` or the matching model statistics |
| expects 256×256 RGB | Size, camera views and rotation | Use the LIBERO 256px pipeline, not 224px preprocessing |
| EGL / OpenGL initialization failure | JetPack, drivers, MuJoCo and renderer | Check EGL and PYOPENGL_PLATFORM; validate simulation independently |
| Many hold_steps | Control gaps, round trip, stale chunks and simulation load | Inspect stage timings, adjust scheduling/rate limits, then recheck success |
| Missing comparison | Metadata status is failed | Find the first exception; partial mode outputs are not a complete run |
| Video appears too fast | Fixed-FPS versus real-time export | Use `*_realtime.mp4` to retain wall-clock waits |
| Low allocator usage but high system memory | Shared-memory accounting | Record Jetson system memory, process and simulation usage together |

## Minimal checks

```bash
python -m pip check
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
curl http://192.168.123.38:8765/health
bash scripts/libero/run_async_benchmark.sh --preflight
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes sync
```

## Latency stress test

```bash
bash scripts/libero/run_async_benchmark.sh \
  --task_ids 0 --modes sync replace blend --extra_delay_s 0.2
```

`extra_delay_s` injects software delay; it does not simulate packet loss or bandwidth constraints. Report the injected value, hold steps, stale chunks and success, not just mean response latency.
