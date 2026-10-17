---
title: Project overview
---

# Two devices. One closed loop.

<p class="lead">TurboVLA-SplitInfer keeps observation preprocessing and action execution on Orin Nano 8GB, and runs the complete vision-language-action model on Thor 128GB. Compare synchronous inference, asynchronous replacement and asynchronous blending on the same evaluation framework.</p>

<div class="home-links">

[Deploy the system](./guide/deployment.md) · [Explore the code](./guide/completeness.md)

</div>

<SystemOverview />

<div class="github-only">

![Orin Nano and Thor split-inference framework](../assets/diagrams/split-inference/framework-flat.png)

</div>

## Hardware deployment

The project is deployed on two physical devices: **Jetson Orin Nano 8GB and Jetson Thor 128GB**, serving as the observation/control device and the complete-model inference device.

<DeploymentGallery />

<div class="github-only">

| Jetson Orin Nano · 8GB | Jetson Thor · 128GB |
| --- | --- |
| ![Orin deployment photograph, background cleaned](../assets/realpics/cleaned/orin-clean.jpg) | ![Thor deployment photograph, background cleaned](../assets/realpics/cleaned/thor-clean.jpg) |
| Observation preprocessing, scheduling and execution | Complete model inference and action conversion |

DDS was used to remove clutter and surface marks. Originals: [Orin](../assets/realpics/orin.jpg) · [Thor](../assets/realpics/Thor.jpg).

</div>

See [device deployment](./guide/deployment.md) for setup and [validation](./guide/validation.md) for recorded results.

## Simulation in action

**Local Orin / Sync / Async / Blend**, shown in a 2×2 comparison of the cabinet-to-plate task. Environment and wrist views are preserved. Independent runs are aligned at their start and replayed at **1× wall-clock speed**, with live execution, inference-wait, background-inference and success indicators.

[![Four-mode real-time LIBERO comparison](../assets/simulation/libero-four-mode-realtime.gif)](../assets/simulation/libero-four-mode-realtime.gif)

## Understand the split

Devices exchange **normalized images, an 8-D state and a language instruction**. DINOv3, BERT, vision-language interaction, state projection and the ACT decoder all run on Thor. Orin does not load model weights in remote mode. The response is a **12 × 7 action chunk** ready for LIBERO execution.

The current split v1 path uses LIBERO relative actions. The repository also retains RoboTwin training/evaluation entry points; their three-view, 50-step, 14-D action interface is separate from split v1.

## Compare three scheduling policies

<TimelineDemo />

| Mode | Purpose | Behavior |
| --- | --- | --- |
| Sync | Blocking baseline | Exhaust a chunk, then request the next |
| Async / `replace` | Infer while actions execute | Trim stale actions and replace the future timeline |
| Blend | Reduce abrupt command changes | Blend six pose dimensions over the overlap; switch the gripper discretely |

Evaluate success, control-interval p95 and response latency under matching configurations.

## Measured results

[Compare Orin / Thor local and Sync / Async / Blend](./guide/benchmark-results.md). Explore the latest comparison, per-task records and JSON/CSV downloads.

## Shortest validation path

1. Prepare dependencies, models and LIBERO assets using the [deployment guide](./guide/deployment.md).
2. Start Thor and run Orin's `--preflight`.
3. Validate all three modes on one task, then add tasks and repetitions.
4. Check success, control-interval p95, hold steps and raw records using the [validation guide](./guide/validation.md).

## Documentation map

| Question | Page |
| --- | --- |
| What runs on each device? | [Architecture](./guide/architecture.md) |
| How are actions aligned and blended? | [Scheduling](./guide/scheduling.md) |
| Where are the entry points and tests? | [Code coverage](./guide/completeness.md) |
| What capabilities does the system provide? | [System capabilities](./guide/capabilities.md) |
