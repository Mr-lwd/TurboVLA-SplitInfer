"""Import measured runs into a portable catalog; build README/site tables and figures.

The catalog contains validated aggregate/episode records and source hashes.
Raw outputs can be versioned separately; building the catalog needs no raw outputs.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.libero.benchmark_common import summarize
from scripts.libero.plot_stage_timings import plot_stage_timings

REPORTS = ROOT / "reports/evaluation"
CATALOG = REPORTS / "catalog.json"
CONFIG_KEYS = ("task_suite_name", "precision", "seed", "chunk_size", "num_open_loop_steps",
               "stats_key", "env_img_res", "num_steps_wait", "num_trials_per_task", "control_mode")
METRICS = ("episodes", "successes", "executed_steps", "rollout_wall_time_s", "all_calls",
           "filtered_calls", "first_call_per_episode", "control_intervals", "hold_steps",
           "expired_chunks", "bootstrap_wait_s", "blocking_wait_after_bootstrap_s",
           "worker_drain_after_episode_s", "env_overlap_fraction_of_inference",
           "arm_action_changes", "remote_stage_timings")
LABELS = {"sync": "Sync", "replace": "Async / replace", "blend": "Blend"}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def verify(actual, recorded, path="summary"):
    """Check published metrics against raw records, including nested distributions."""
    if isinstance(actual, dict):
        for key, value in actual.items():
            if key in recorded:
                verify(value, recorded[key], f"{path}.{key}")
    elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if not isinstance(recorded, (int, float)) or not math.isclose(actual, recorded, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError(f"Recorded metric disagrees with raw data: {path}")
    elif actual != recorded:
        raise ValueError(f"Recorded metric disagrees with raw data: {path}")


def import_run(directory):
    directory = Path(directory).resolve()
    metadata_files = list(directory.glob("*_metadata.json"))
    if len(metadata_files) != 1:
        raise ValueError("Each run must contain exactly one *_metadata.json")
    meta_path = metadata_files[0]
    name = meta_path.name.removesuffix("_metadata.json")
    sources = []
    def read(path):
        raw = path.read_bytes()
        sources.append({"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw)
    metadata = read(meta_path)
    if metadata.get("status") != "completed":
        raise ValueError("Only completed runs may be published")
    config = metadata["config"]
    exclude = metadata.get("exclude_first_calls_per_episode")
    if exclude is None:
        settings = metadata.get("base_config", metadata.get("config_file_contents", {}))
        exclude = settings.get("benchmark", {}).get("exclude_first_calls")
    if type(exclude) is not int or exclude < 0:
        raise ValueError("Missing/invalid per-episode first-call filter in metadata")
    is_remote = bool(config.get("remote_policy_url"))
    records = []
    modes = metadata.get("experiment", {}).get("modes", []) if is_remote else ["local"]
    if not modes or any(mode not in (*LABELS, "local") for mode in modes):
        raise ValueError("Unsupported benchmark modes")
    for mode in modes:
        suffix = f"_{mode}" if is_remote else ""
        raw = read(directory / f"{name}{suffix}.json")
        saved = read(directory / f"{name}{suffix}_summary.json")
        if is_remote:
            from scripts.libero.benchmark_async import summarize_episodes
            if raw["mode"] != mode:
                raise ValueError("Mode does not match filename")
            episodes = raw["episodes"]
            summary = summarize_episodes(episodes, exclude)
            for episode in episodes:
                if len(episode["step_timings"]) != episode["executed_steps"]:
                    raise ValueError("Control-step count mismatch")
        else:
            if raw.get("policy_backend") != "local":
                raise ValueError("Expected local result")
            summary, _ = summarize(raw, exclude)
            episodes = [{"task_id": task["task_id"], "instruction": task["task_description"], **episode}
                        for task in raw["tasks"] for episode in task["episode_results"]]
            summary.update(episodes=len(episodes), successes=sum(e["success"] for e in episodes))
        # Verify existing recorded fields, never substitute a fresh measurement.
        verify({key: summary.get(key) for key in METRICS if key in saved}, saved)
        if not episodes or len({(e["task_id"], e["episode"]) for e in episodes}) != len(episodes):
            raise ValueError("Empty/duplicate episode records")
        if summary["executed_steps"] != sum(e["executed_steps"] for e in episodes):
            raise ValueError("Executed-step total mismatch")
        if not is_remote:
            verify(summary["successes"], raw["total_successes"], "total_successes")
            verify(len(episodes), raw["total_episodes"], "total_episodes")
        detail = []
        for e in episodes:
            detail.append({"task_id": e["task_id"], "episode": e["episode"], "instruction": e["instruction"],
                           "success": e["success"], "steps": e["executed_steps"], "wall_s": e["rollout_wall_time_s"],
                           "calls": len(e["inference_timings"]),
                           "hold_steps": sum(s["hold"] for s in e["step_timings"]) if "step_timings" in e else None})
        records.append({"mode": mode, "label": LABELS.get(mode, f"{metadata['device_name'].title()} local"),
                        "metrics": {key: summary.get(key) for key in METRICS}, "episodes": detail})
    server = metadata.get("remote_server", {})
    runtime = server.get("runtime")
    if runtime is not None:
        runtime = {key: runtime.get(key) for key in ("python", "torch", "cuda", "packages", "platform", "nvpmodel")}
    source_dir = str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else directory.name
    return {"id": name, "kind": "remote" if is_remote else "local", "source_directory": source_dir,
            "source_files": sources, "config": {key: config.get(key) for key in CONFIG_KEYS},
            "experiment": {key: value for key, value in metadata.get("experiment", {}).items() if key != "output_root"},
            "exclude_first_calls": exclude,
            "hardware": {key: metadata.get(key) for key in ("device_name", "gpu_name", "board", "nvpmodel", "torch", "cuda", "packages")},
            "server": {"gpu_name": server.get("gpu_name"), "checkpoint_sha256": server.get("checkpoint_sha256"), "runtime": runtime},
            "checkpoint_name": server.get("checkpoint_name") or Path(config.get("ckpt_path", "")).name,
            "git_commit": metadata.get("git_commit"), "git_dirty": bool(metadata.get("git_status")),
            "compression": metadata.get("compression"), "records": records}


def add_run(catalog, run, group_id, title=None):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", group_id):
        raise ValueError("group must contain lowercase letters, digits, hyphens or underscores")
    groups = catalog["groups"]
    group = next((g for g in groups if g["id"] == group_id), None)
    if group is None:
        group = {"id": group_id, "title": title or group_id, "run_ids": []}
        groups.append(group)
    elif title:
        group["title"] = title
    existing = next((r for r in catalog["runs"] if r["id"] == run["id"]), None)
    if existing is not None and existing != run:
        raise ValueError("Run ID already exists with different data; preserve provenance with a new run ID")
    if existing is None:
        catalog["runs"].append(run)
    if run["id"] not in group["run_ids"]:
        group["run_ids"].append(run["id"])
    catalog.setdefault("featured_group", group_id)


def group_rows(catalog, group):
    runs = {run["id"]: run for run in catalog["runs"]}
    return [(runs[id_], record) for id_ in group["run_ids"] for record in runs[id_]["records"]]


def number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def table(rows):
    lines = ["| 设备 / 模式 | 成功 | 执行步数 | 任务总耗时 / s | 平均推理响应时间¹ / ms | 推理响应时间 p95¹ / ms | 控制间隔 p95 / ms | hold 步 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for _, record in rows:
        s = record["metrics"]
        lines.append(f"| {record['label']} | {s['successes']}/{s['episodes']} | {s['executed_steps']} | "
                     f"{number(s['rollout_wall_time_s'])} | {number(s['filtered_calls']['mean_ms'])} | "
                     f"{number(s['filtered_calls']['p95_ms'])} | {number((s['control_intervals'] or {}).get('p95_ms'))} | "
                     f"{number(s['hold_steps'], 0)} |")
    return "\n".join(lines)


def plot_group(rows, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "svg.hashsalt": "turbovla-benchmark"})
    labels = [r["label"] for _, r in rows]
    colors = [{"local": "#60758a", "sync": "#d18236", "replace": "#297fa4", "blend": "#41876a"}[r["mode"]] for _, r in rows]
    specs = [("Task success", lambda m: 100*m['successes']/m['episodes'], "%", 0),
             ("Total task execution time", lambda m: m['rollout_wall_time_s'], "seconds", 2),
             ("Mean inference response time", lambda m: m['filtered_calls']['mean_ms'], "ms / chunk", 2),
             ("Control interval p95", lambda m: (m['control_intervals'] or {}).get('p95_ms'), "ms", 2)]
    fig, axes = plt.subplots(2, 2, figsize=(12, max(6.7, len(rows)*.65+3.5)), layout="constrained")
    for ax, (heading, get, unit, digits) in zip(axes.flat, specs):
        values = [get(r['metrics']) for _, r in rows]
        maximum = max((v for v in values if v is not None), default=1) or 1
        ax.barh(range(len(rows)), [v or 0 for v in values], color=colors, height=.55)
        for i, value in enumerate(values):
            label = "not recorded" if value is None else f"{value:.{digits}f}"
            if unit == "%":
                m=rows[i][1]['metrics']; label += f"% ({m['successes']}/{m['episodes']})"
            ax.text((value or 0)+maximum*.025, i, label, va="center", fontsize=10)
        ax.set(yticks=range(len(rows)), yticklabels=labels, xlabel=unit, title=heading, xlim=(0, maximum*1.48))
        if unit == '%':
            ax.set_xticks([0, 25, 50, 75, 100])
            ax.spines['bottom'].set_bounds(0, 100)
        ax.invert_yaxis()
        ax.spines[['top','right','left']].set_visible(False)
        ax.set_axisbelow(True); ax.grid(axis='x', color='#e3eaf0')
    fig.suptitle(title, fontsize=15, weight="bold")
    fig.supxlabel("Recorded runs; different trajectories. Missing values are not zero. Call filtering: see run metadata.", fontsize=10)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix('.svg'), metadata={'Date': None})
    fig.savefig(path.with_suffix('.png'), dpi=160)
    plt.close(fig)


def replace_block(text, start, end, content):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Expected one generated results marker pair in README")
    before, rest = text.split(start)
    _, after = rest.split(end)
    return before + start + "\n\n" + content + "\n\n" + end + after


def build(catalog):
    all_rows = []
    page = ["# 实测数据", "", "数据来自已完成的运行记录；下表与图由同一份可追加的数据目录生成。Async 对应 CLI 的 `replace`。", "",
            "<BenchmarkDashboard />", "", "## 静态对照与下载", "",
            "¹ 推理响应时间的均值和 p95 均按每个 episode 排除前 N 次调用后汇总；N 见来源表。推理响应时间是从发起策略调用到收到整块动作的耗时；远程模式包含预处理、传输和服务端推理，不是每步耗时。`—` 表示原记录缺失。", "",
            "[下载结构化数据](../../reports/evaluation/catalog.json) · [下载汇总 CSV](../../reports/evaluation/summary.csv)", ""]
    featured = None
    for group in catalog['groups']:
        rows = group_rows(catalog, group)
        image_name = group['id']
        plot_group(rows, ROOT / f"assets/benchmarks/{image_name}", group['id'])
        stage_chart = plot_stage_timings(rows, ROOT / f"assets/benchmarks/{image_name}-stages")
        page += [f"## {group['title']}", "", table(rows), "",
                 f"![{group['title']} 四项指标](../../assets/benchmarks/{image_name}.svg)", ""]
        page += [f"- {note}" for note in group.get('notes', [])] + [""]
        runs = [r for r in catalog['runs'] if r['id'] in group['run_ids']]
        mismatches = [key for key in CONFIG_KEYS if len({json.dumps(r['config'][key]) for r in runs}) > 1]
        if mismatches:
            page += ["**本组配置存在差异：" + ", ".join(mismatches) + "。仅并列展示，不视为受控对照。**", ""]
        page += ["### 调度与调用明细", "",
                 "| 模式 | 调用总数 / 过滤后 | 首次推理平均响应时间 / ms | 首段后阻塞 / s | 推理与 env.step 重叠比例 | drain / s | 指令变化 L2 p95 |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for _, record in rows:
            m=record['metrics']; overlap=m['env_overlap_fraction_of_inference']
            page += [f"| {record['label']} | {m['all_calls']['count']} / {m['filtered_calls']['count']} | "
                     f"{number(m['first_call_per_episode']['mean_ms'])} | {number(m['blocking_wait_after_bootstrap_s'],3)} | "
                     f"{number(100*overlap if overlap is not None else None)} | {number(m['worker_drain_after_episode_s'],3)} | "
                     f"{number((m['arm_action_changes'] or {}).get('p95_action_l2'),3)} |"]
        page += ["", "重叠比例单位为 %；L2 是相邻六维相对指令差值，混合了平移/旋转单位，不是物理 jerk。", "",
                 "### 远程调用分阶段均值（过滤后，ms）", ""]
        if stage_chart:
            page += [f"![三种协同模式的推理响应时间构成](../../assets/benchmarks/{image_name}-stages.svg)", "",
                     f"[下载 SVG](../../assets/benchmarks/{image_name}-stages.svg) · [下载 PNG](../../assets/benchmarks/{image_name}-stages.png)", "",
                     "堆叠图仅相加互不重叠阶段的均值；往返时间已分解为 Thor 处理与 HTTP/传输等开销，不重复叠加。响应 p95 单独列出。缺少阶段或样本数不一致时不绘制该模式的分解。", ""]
        page += ["| 模式 | Orin 预处理 | 编码/压缩 | 往返 | Thor 推理与动作转换 | HTTP/传输残差 |",
                 "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for _, record in rows:
            stages=record['metrics']['remote_stage_timings']
            if stages:
                values=[number(stages[key]['filtered_calls']['mean_ms']) for key in
                        ('client_preprocess_s','client_encode_s','round_trip_s','server_inference_s','transport_overhead_s')]
                page += [f"| {record['label']} | " + ' | '.join(values) + ' |']
        page += ["", "往返包含 Thor 处理，传输残差含 HTTP/响应开销；阶段不可全部相加。", "", "### 数据来源", ""]
        page += ["| 来源运行 | 配置 | 每回合排除调用数 |", "| --- | --- | ---: |"]
        for run in [r for r in catalog['runs'] if r['id'] in group['run_ids']]:
            c=run['config']
            page += [f"| `{run['id']}` | {c['task_suite_name']} / {c['precision']} / seed {c['seed']} / chunk {c['chunk_size']} | {run['exclude_first_calls']} |"]
        page += ["", "### 逐任务结果", "",
                 "| 模式 | task ID | episode | 成功 | 步数 | 任务耗时 / s | hold 步 |",
                 "| --- | ---: | ---: | --- | ---: | ---: | ---: |"]
        for run, record in rows:
            s=record['metrics']
            all_rows.append({'group':group['id'], 'run_id':run['id'], 'mode':record['mode'], 'label':record['label'],
                'suite':run['config']['task_suite_name'], 'precision':run['config']['precision'], 'seed':run['config']['seed'],
                'episodes':s['episodes'], 'successes':s['successes'], 'executed_steps':s['executed_steps'],
                'rollout_wall_time_s':s['rollout_wall_time_s'], 'all_calls':s['all_calls']['count'],
                'filtered_call_count':s['filtered_calls']['count'], 'filtered_call_mean_ms':s['filtered_calls']['mean_ms'],
                'filtered_call_p95_ms':s['filtered_calls']['p95_ms'], 'control_interval_p95_ms':(s['control_intervals'] or {}).get('p95_ms'),
                'hold_steps':s['hold_steps'], 'bootstrap_wait_s':s['bootstrap_wait_s'],
                'blocking_wait_after_bootstrap_s':s['blocking_wait_after_bootstrap_s'],
                'worker_drain_s':s['worker_drain_after_episode_s']})
            for e in record['episodes']:
                page += [f"| {record['label']} | {e['task_id']} | {e['episode']} | {'是' if e['success'] else '否'} | {e['steps']} | {number(e['wall_s'])} | {number(e['hold_steps'],0)} |"]
        page += [""]
        if group['id'] == catalog['featured_group']:
            featured = (f"**{group['title']}**\n\n" + table(rows) + "\n\n¹ 每个 episode 的首次调用筛选数见数据页；`—` 表示未记录。推理响应时间按整块动作统计，远程模式包含预处理、传输和服务端推理。\n\n"
                        +f"![实测指标对比](assets/benchmarks/{image_name}.svg)\n\n"
                        +"[详细数据、口径与后续追加方式](docs-site/guide/benchmark-results.md) · [JSON 数据](reports/evaluation/catalog.json) · [CSV 汇总](reports/evaluation/summary.csv)")
            if stage_chart:
                featured += ("\n\n**协同推理耗时构成**\n\n"
                             + f"![协同推理分阶段耗时](assets/benchmarks/{image_name}-stages.svg)\n\n"
                             + "每段为相同过滤样本的平均耗时，合计为完整推理响应时间；往返已拆分，不重复计入。HTTP / 传输等开销包含接收等待与系统开销，并非纯网络延迟。\n\n"
                             + f"[下载 SVG](assets/benchmarks/{image_name}-stages.svg) · [下载 PNG](assets/benchmarks/{image_name}-stages.png)")
    if featured is None:
        raise ValueError("featured_group does not exist")
    page += ["## 口径与追加方法", "", "见[数据维护说明](./benchmark-data.md)。每组保留独立运行和逐任务结果，不自动合并不同 seed、任务集、设备或延迟设置。原始评测文件位于可提交的 `outputs/`，精简数据目录记录来源文件名及 SHA-256，重建网页无需访问原始文件。", ""]
    (ROOT/'docs-site/guide/benchmark-results.md').write_text('\n'.join(page))
    with (REPORTS/'summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(all_rows[0]),lineterminator='\n'); writer.writeheader(); writer.writerows(all_rows)
    readme=ROOT/'README.md'
    readme.write_text(replace_block(readme.read_text(), '<!-- BENCHMARK_RESULTS_START -->', '<!-- BENCHMARK_RESULTS_END -->', featured))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    add=sub.add_parser('add',help='Validate and import a completed local or async run')
    add.add_argument('run_dir',type=Path); add.add_argument('--group',required=True); add.add_argument('--title')
    sub.add_parser('build',help='Regenerate figures, tables and README from the published catalog')
    args=parser.parse_args()
    catalog=json.loads(CATALOG.read_text()) if CATALOG.exists() else {'schema_version':1,'groups':[],'runs':[]}
    if args.command=='add':
        add_run(catalog,import_run(args.run_dir),args.group,args.title)
        write_json(CATALOG,catalog)
        print(f'Imported {args.run_dir.name}; run build to update documentation.')
    else:
        build(catalog); print('Updated benchmark figures, CSV, README and documentation.')


if __name__=='__main__':
    main()
