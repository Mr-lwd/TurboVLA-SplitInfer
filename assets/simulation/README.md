# LIBERO 四模式实时仿真对比

[查看 2×2 GIF](libero-four-mode-realtime.gif)：左上 Local Orin，右上 Sync，左下 Async，右下 Blend。四段独立运行均为 LIBERO Spatial 任务 9、episode 0，成功完成“从木柜上取黑碗并放到盘中”。

排除任务 0 的首次调用长等待及未共同成功的任务后，选用完成时间差异更清楚的任务 9：Local Orin 9.33 s、Sync 10.37 s、Async 8.21 s、Blend 8.57 s。

- 统一按各次 rollout 起点对齐，以墙钟 1×、20 FPS 回放，包含首次推理等待；各模式完成后保持终帧至本轮结束。
- 每格保留原始 512×256 环境与腕部双视角；合成画面为 1060×756。原录像顶部已有状态条替换为视角标签，中文状态另置于画面上方。
- 状态由原始 JSON 的推理区间、阻塞等待与控制步记录生成；颜色分别表示执行、等待推理、执行＋后台推理和任务成功。“执行”指控制执行阶段，包含控制节拍间隔。
- [来源与时间清单](libero-four-mode-realtime.json)记录四段实时录像、原始 JSON 路径及任务耗时。该 GIF 为单任务演示，整体性能见[实测数据](../../docs-site/guide/benchmark-results.md)。

复现导出（需要 Pillow 与 imageio-ffmpeg；Linux 下通过 `--font` 指定中文字体）：

```bash
python scripts/libero/build_simulation_gif.py --task-id 9
```
