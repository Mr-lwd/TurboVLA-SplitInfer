# English diagram delivery

| File | Purpose |
| --- | --- |
| `framework-flat.png` | Two-device framework, exported from native editable objects |
| `pipeline-flat.png` | Async / Blend / Sync pipeline overview |
| `turbovla-diagrams-editable.pptx` | Two editable slides with English text |
| `animations/*.gif` | Deterministic scheduling illustrations |
| `animations/*-poster.png` | Corresponding still frames |
| `animations/schedule.json` | Illustrative scheduling sequence used by the animation generator |

The original diagrams were generated through codex-ppt with DDS / gpt-image-2.5-sunburst, then reconstructed through image-to-editable-ppt. As authorized for this edition, the existing native PowerPoint objects were copied and translated into English; no new image-generation call was needed.

The architecture slide contains 46 text objects, 57 shapes and three independently movable icons. The pipeline slide contains 108 text objects and 92 shapes. No full-slide raster is used as an editable-text background. The request and return paths remain continuous native arrows. English text uses Arial; both PNG exports are 3840×2160.

All neural layers run on Thor. Orin handles observations, scheduling and execution. Capacity labels are device memory capacities, not measured model consumption. The 20 Hz setting is a control-rate cap. Pipeline units are illustrative, not measured latency.

The PPTX is self-contained and opens in PowerPoint. Its package, English text, slide/object counts and full-resolution slide exports were checked. Original Chinese deliverables are backed up outside the repository; this directory contains the current English publication files only.
