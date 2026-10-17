# Design notes

- Audience: developers reproducing the system and reviewers examining its implementation and evidence.
- Priority: make the device boundary and experiment workflow clear through concise technical documentation.
- Foundation: VitePress default theme (MIT), preserving sidebar, local search, keyboard navigation and mobile navigation.
- Visual language: white background, near-black text and pale-blue panels; left-aligned headings, restrained borders and no decorative gradients.
- Device-specific content: Orin Nano 8GB, Thor 128GB, complete model on Thor, dual views, 256px images, 8-D state, 12×7 actions, R=4, B=3 and one in-flight request.
- Interactivity: scheduling mode buttons, delay slider, benchmark metric selection and per-task records. Pipeline animations start from a still frame and can be played or stopped.
- Accessibility: visible keyboard focus, readable text, responsive layouts and reduced-motion support. Wide timelines and detailed charts use labeled horizontal scrolling.
- Photographs: project hardware images cleaned through DDS; original photos remain linked. No external stock hardware photos are substituted.
- Diagrams: originally generated through codex-ppt/DDS and rebuilt with image-to-editable-ppt. The English edition translates the existing editable objects and exports matching PNGs.
- Animations: deterministic scheduling illustrations are separate from measured LIBERO wall-clock playback. Both use English labels; their timing scopes are explicitly stated.
- Benchmarks: consistent muted colors for Orin, Thor, Sync, Async and Blend. Details and methodology expand on demand. Only the current comparison is published.

The initial design review used Taste Skill's `product-performs` direction, adapted to documentation rather than a marketing landing page. The user's compact white/blue design requirements take precedence over unrelated promotional patterns.

All maintained page text and visual labels use English. Original run identifiers, raw source records, hashes and upstream attribution are preserved. Temporary translation files, renders and QA evidence stay outside published assets or in ignored `qa/` directories.
