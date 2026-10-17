# 故障排查

按错误发生位置定位，优先检查 metadata 和 Thor 日志。避免同时改模型、精度与调度参数，导致无法归因。

| 现象 | 优先检查 | 处理 |
| --- | --- | --- |
| 连接失败 / 超时 | Thor 是否 READY、IP/端口、监听网卡、两端网络 | 校正 THOR_HOST / THOR_URL，保留错误日志后重启实验 |
| precision / chunk_size mismatch | 客户端与服务元数据 | 使用相同配置；split v1 需要 LIBERO 12×7 |
| server instance changed | 服务是否中途重启 | 重新连接并开始新的实验，不继续旧 episode |
| stats_key mismatch | stats 文件与 key | 统一 `libero_all4_no_noops` 或对应模型统计 |
| expects 256×256 RGB | 图像尺寸、视角与旋转 | 保持 LIBERO 256px 管线，不使用 224px 预处理 |
| EGL / OpenGL 初始化失败 | JetPack、驱动、MuJoCo、渲染环境 | 检查 EGL 与 PYOPENGL_PLATFORM，先单独验证仿真 |
| hold_steps 较多 | 控制间隔、往返、过期块、仿真负载 | 分析阶段耗时后调整请求间隔/控制上限，重新比较成功率 |
| 没有 comparison | metadata 是否 failed | 查最初异常；已有单模式文件不视为完整实验 |
| 视频看起来很快 | 是否打开普通固定 FPS 视频 | 使用 `*_realtime.mp4` 检查墙钟等待 |
| 显存很小但系统内存紧张 | allocator 与共享内存口径不同 | 同时采集 Jetson 系统内存与进程/仿真占用 |

## 最小排查命令

```bash
python -m pip check
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
curl http://192.168.123.38:8765/health
bash scripts/libero/run_async_benchmark.sh --preflight
bash scripts/libero/run_async_benchmark.sh --task_ids 0 --modes sync
```

## 延迟压力实验

```bash
bash scripts/libero/run_async_benchmark.sh \
  --task_ids 0 --modes sync replace blend --extra_delay_s 0.2
```

`extra_delay_s` 是软件注入延迟，不代表真实网络丢包或带宽限制。报告中应注明注入值，检查 hold、过期动作块与成功率，而不只看推理均值。
