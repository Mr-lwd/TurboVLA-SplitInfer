# Sync / Blend / Async

网站与图稿使用 **Async** 表示异步直接替换；实际命令行名称为 **`replace`**。`blend` 同样使用异步调度，只改变动作块合并策略。

## 三模式流水线总览

![Async、Blend、Sync 三种协同推理流水线，含 Thor 推理与 Orin 执行、动作裁剪和融合权重](../../../assets/diagrams/split-inference/pipeline-flat.png)

[下载两页可编辑 PPT](../../../assets/diagrams/split-inference/turbovla-diagrams-editable.pptx)

上述流水线图由 DDS 图稿重建为原生纯色对象。下面的动图按同一调度序列绘制，逐步展示控制推进与请求重叠。所有时间单位均为示意。

<TimelineDemo />

## 流水线动图

<PipelineAnimation />

<div class="github-only">

**Async · 异步替换**

![Async：后台推理、过期前缀裁剪与未来动作替换](../../../assets/diagrams/split-inference/animations/pipeline-async.gif)

**Blend · 异步融合**

![Blend：后台推理与三步新旧动作融合](../../../assets/diagrams/split-inference/animations/pipeline-blend.gif)

**Sync · 同步推理**

![Sync：执行动作块、阻塞等待与继续执行](../../../assets/diagrams/split-inference/animations/pipeline-sync.gif)

[三模式对照动图](../../../assets/diagrams/split-inference/animations/pipeline-comparison.gif)

</div>

蓝色推理块在 Thor，动作序列在 Orin。三行使用同一示意墙钟时间轴；sync 的等待段保持实际控制步不变，async 与 blend 则继续执行已有动作。默认 `H=12 / R=4 / B=3`；动画显示重复重规划，而不是只展示一次请求。

## 共同规则

- 第一次预测阻塞等待，建立初始动作块。
- 默认块长 `H=12`，异步每 `R=4` 个实际控制步尝试重规划，融合窗 `B=3`。
- 最多一个请求在途；后台输入使用观测副本，避免环境复用图像缓冲区。
- 新动作依据**已执行控制步**对齐，不用 HTTP 耗时除以 50 ms 推算。
- 控制上限为 20 Hz；仿真慢时不跳步、不追赶。

## Sync：阻塞基线

当前动作块执行完毕后，获取新的观测并请求下一块。等待期间不推进 `env.step()`。它的阻塞等待应在墙钟视频中保留，不能用固定 FPS 的回放掩盖。

```bash
bash scripts/libero/run_async_benchmark.sh --modes sync
```

## Async：对齐后替换

后台预测时继续执行旧块。设采样步为 `s`、返回时实际控制步为 `t`，裁掉新块的前 `min(t-s, H)` 项，再将剩余动作写入未来时间线；旧未来动作（含旧尾部）整体被替换。

例如在步 4 采样、步 6 合并，新块 B 的 `B0、B1` 过期，从 `B2` 开始应用。若 `t-s ≥ H`，整块丢弃，不破坏仍有效的旧未来动作。

```bash
bash scripts/libero/run_async_benchmark.sh --modes replace
```

## Blend：重叠区渐变

先执行同样的过期裁剪，再求新旧时间线的连续重叠长度 `O`，最大为 `blend_steps`。重叠区第 `i` 项的权重为 `α=(i+1)/O`：

```text
arm = (1 − α) × old_arm + α × new_arm
gripper = new_gripper if α ≥ 0.5 else old_gripper
```

完整三步重叠时，权重为 `1/3 → 2/3 → 1`。只有两步重叠时是 `1/2 → 1`；无重叠时直接采用新动作。前六维为相对位姿指令，夹爪不生成中间值。

```bash
bash scripts/libero/run_async_benchmark.sh --modes blend --blend_steps 3
```

## 缓冲耗尽与错误

异步等待期间若当前步没有动作，输出零手臂增量，保持上一夹爪命令，并计入 `hold_steps`。若请求最终失败，异常向上抛出；不会静默切到本地模型，也不会无限使用旧动作。

这一策略是 LIBERO 仿真的缓冲退化行为，不包含真机限位、碰撞检测、独立急停和通信失联看门狗。长时延可通过 `--extra_delay_s` 实验观察。

## 比较时看什么

| 问题 | 观察量 |
| --- | --- |
| 是否完成任务 | `success_rate` |
| 控制节奏是否稳定 | `control_intervals.p95_ms`、`control_lateness` |
| 是否经常用尽缓冲 | `hold_steps`、`expired_chunks` |
| 指令变化是否变小 | `arm_action_changes`；这是混合单位指令 L2，不是 jerk |
| 是否缩短任务总时间 | `rollout_wall_time_s`，同时保留成功率 |

Blend 是推理阶段的启发式融合，没有重新训练、延迟条件模型或 RTC 机制。它可能改善指令切换，也可能影响任务成功率，需要实测判断。
