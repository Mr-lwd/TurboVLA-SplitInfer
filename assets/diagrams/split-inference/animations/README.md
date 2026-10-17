# Scheduling animations

| File | Purpose |
| --- | --- |
| `pipeline-comparison.gif` | All modes on a common illustrative wall-clock timeline |
| `pipeline-async.gif` | Background inference and direct replacement (`replace`) |
| `pipeline-blend.gif` | Aligned three-step blending, with old/new action indices |
| `pipeline-sync.gif` | Blocking requests after chunk exhaustion |
| `*-poster.png` | Still frames for previews and stopped playback |
| `schedule.json` | Deterministic event sequence |

The example uses H=12, R=4 and B=3, with an assumed two-unit inference delay. These are illustrative units, not device measurements. An asynchronous response arrives after two executed control steps, so its first two actions are stale. Sync does not advance the environment while waiting and starts at the new chunk's zeroth action.

All modes block for initialization. Async/Blend requests B, C and D are issued at control steps 4, 8 and 12. The first six action dimensions use new-action weights 1/3 → 2/3 → 1; the gripper switches to the new command at alpha ≥ 0.5.

Each GIF contains 91 frames and loops, with a two-second final hold. Rebuild the English illustrations with:

```bash
python scripts/docs/render_pipeline_animations.py
```

The generator requires Pillow and Matplotlib, using bundled DejaVu fonts. It draws the scheduling illustration directly; it does not modify deployment photographs or reconstruct slide artwork.
