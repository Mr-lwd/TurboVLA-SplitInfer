# Four-mode real-time LIBERO comparison

[View the 2×2 GIF](libero-four-mode-realtime.gif): Local Orin at top left, Sync at top right, Async at bottom left and Blend at bottom right. All four independent runs successfully complete LIBERO Spatial task 9, episode 0: pick up the black bowl on the wooden cabinet and place it on the plate.

Task 0 is excluded because of its long initial call. Among commonly successful remaining tasks, task 9 offers a clear timing contrast: Local Orin 9.33 s, Sync 10.37 s, Async 8.21 s and Blend 8.57 s.

- Runs are aligned at rollout start and replayed at 1× wall-clock speed, 20 FPS, retaining all inference waits. Completed modes hold their terminal frame until the shared loop ends.
- Each panel preserves the original 512×256 environment/wrist views; the composite is 1060×756. The existing video status strip is replaced by view labels, with English state labels above each panel.
- States follow recorded inference intervals, blocking waits and control steps: executing, waiting for inference, executing with background inference, hold, and success. Execution includes control pacing intervals.
- [Source and timing manifest](libero-four-mode-realtime.json) records video/JSON paths and durations. This is a single-task demonstration; aggregate performance is reported in the [benchmarks](../../docs-site/guide/benchmark-results.md).

Rebuild with Pillow, imageio-ffmpeg and Matplotlib; English fonts are bundled with Matplotlib:

```bash
python scripts/libero/build_simulation_gif.py --task-id 9
```
