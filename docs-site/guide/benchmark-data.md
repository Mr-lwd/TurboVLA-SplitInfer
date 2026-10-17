# 实测数据维护

网站和 README 只展示当前最新对照，图表和页面使用设备、模式名称，不使用日期标签或实验分组菜单。

## 当前数据

当前对照为 Orin 本机、Thor 本机、Sync、Async / replace、Blend **共同成功的 9 个案例**。
按 `(task_id, episode)` 对齐，保留 task **0、1、2、3、5、6、7、8、9**，episode 均为 0。
Thor 本机与 Sync 的 task 4 失败，因此五种模式统一排除 task 4。

| 模式 | 案例数 | 总耗时 / s | 推理均值 / p95 / ms | 控制间隔 p95 / ms |
| --- | ---: | ---: | ---: | ---: |
| Orin 本机 | 9 | 71.40 | 125.01 / 127.70 | 192.13 |
| Thor 本机 | 9 | 26.95 | 31.15 / 33.36 | 55.83 |
| Sync | 9 | 74.76 | 134.03 / 285.30 | 167.40 |
| Async | 9 | 65.72 | 113.14 / 235.42 | 82.33 |
| Blend | 9 | 65.94 | 116.92 / 226.76 | 81.35 |

## 统计口径

- 推理响应与阶段耗时：选出共同案例后，每回合排除首次调用，再合并剩余样本计算均值与 p95。
- 总耗时、控制间隔、步数、hold、阻塞与重叠比例：均按相同的 9 个案例统计；总耗时包含首次推理等待。
- 共同成功案例数用于时间对照；完整运行成功数依次为 10/10、9/10、9/10、10/10、10/10。
- 本机没有墙钟限频，远程采用 20 Hz 上限。不同轨迹与执行步数的总耗时应结合任务结果比较。
- 远程响应包含 Orin 预处理、编码、HTTP/传输、Thor 解码/排队与推理。阶段均值采用相同样本，合计等于响应均值；p95 独立统计。
- 任务耗时排除模型加载、环境重置、初始稳定等待及视频编码；异步请求的结束等待 `drain` 单列。
- 数据由现有记录重算，未重新运行评测。设备环境、权重记录、运行 ID 和来源 SHA-256 保存在下载 JSON 中。

## 数据文件

| 文件 | 用途 |
| --- | --- |
| `reports/evaluation/catalog.json` | 完整数据目录；`featured_group` 指定当前对照 |
| `reports/evaluation/latest.json` | 当前对照及其来源记录，供网站读取与下载 |
| `reports/evaluation/summary.csv` | 当前对照的逐模式汇总 |
| `assets/benchmarks/` | 当前对照的指标图与耗时构成图 |

报告生成器只发布 `featured_group` 选中的对照。原始记录继续保存在数据目录中，不在网站提供旧实验切换。
页面不显示运行时间标签；JSON 保留原始运行 ID 和哈希，以便追溯。

## 更新最新结果

在仓库根目录执行。制图需要 Matplotlib 和中文字体；Windows 可使用微软雅黑，Ubuntu 可安装 `fonts-noto-cjk`。

```bash
# 导入新一轮完成的运行，将其他设备和模式加入同一个来源集合
python scripts/libero/build_benchmark_report.py add /path/to/completed/run \
  --group spatial-next --title 'LIBERO Spatial'
python scripts/libero/build_benchmark_report.py add /path/to/another/run \
  --group spatial-next

# 计算共同成功案例，并指定为当前展示数据
python scripts/libero/build_benchmark_report.py select-common-success \
  --source-group spatial-next --group spatial-next-common-success --featured

# 同步生成当前 JSON、CSV、图表、README 和文档页
python scripts/libero/build_benchmark_report.py build
```

筛选命令校验任务、seed、原始文件和 SHA-256，不启动模型评测。新数据完成导入与筛选后，重新生成即可替换当前展示；不要手工修改指标或生成区。

已有当前对照时，只需执行 `build` 即可重建展示，无需读取原始 `outputs/` 或运行 GPU 推理。

```bash
cd docs-site
npm ci
npm run check
npm run build
```
