"""Import measured runs into a portable catalog; build README/site tables and figures.

The catalog contains validated aggregate/episode records and source hashes.
Raw outputs can be versioned separately; building the catalog needs no raw outputs.
"""

import argparse
import copy
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
from scripts.libero.plot_stage_timings import latency_breakdown, plot_stage_timings
from scripts.libero.benchmark_style import INK, MUTED, GRID, chart_style, mode_color, mode_label, save_chart

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
    elif group.get("selection"):
        raise ValueError("Add runs to the full source group, then regenerate the selection")
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
    if group.get("selection"):
        return [(runs[item["run_id"]], item["record"]) for item in group["derived_records"]]
    return [(runs[id_], record) for id_ in group["run_ids"] for record in runs[id_]["records"]]


def episode_key(episode):
    return episode["task_id"], episode["episode"]


def common_success_group(catalog, source_id, group_id, root=ROOT):
    """Derive a portable matched cohort from verified raw samples; never run inference."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", group_id) or group_id == source_id:
        raise ValueError("Use a distinct valid group ID")
    source = next(g for g in catalog["groups"] if g["id"] == source_id)
    if source.get("selection"):
        raise ValueError("Select from a full-run group")
    rows = group_rows(catalog, source)
    if not rows:
        raise ValueError("Empty comparison group")
    for key in ("task_suite_name", "seed"):
        values = {run["config"].get(key) for run, _ in rows}
        if None in values or len(values) != 1:
            raise ValueError(f"Matched episodes require the same recorded {key}")
    successful = [{episode_key(e) for e in record["episodes"] if e["success"]} for _, record in rows]
    retained = set.intersection(*successful)
    if not retained:
        raise ValueError("No common successful episodes")
    all_keys = set.union(*[{episode_key(e) for e in record["episodes"]} for _, record in rows])
    verified = set()
    derived = []
    for run, record in rows:
        directory = root / run["source_directory"]
        if run["id"] not in verified:
            current = import_run(directory)
            if current != run:
                raise ValueError(f"Source data changed for {run['id']}; preserve the original provenance")
            verified.add(run["id"])
        suffix = "" if run["kind"] == "local" else f"_{record['mode']}"
        raw = json.loads((directory / f"{run['id']}{suffix}.json").read_text())
        episodes = [e for e in record["episodes"] if episode_key(e) in retained]
        if run["kind"] == "remote":
            from scripts.libero.benchmark_async import summarize_episodes
            summary = summarize_episodes([e for e in raw["episodes"] if episode_key(e) in retained], run["exclude_first_calls"])
        else:
            for task in raw["tasks"]:
                task["episode_results"] = [e for e in task["episode_results"]
                                           if (task["task_id"], e["episode"]) in retained]
            raw["tasks"] = [t for t in raw["tasks"] if t["episode_results"]]
            raw.update(total_episodes=len(episodes), total_successes=len(episodes), overall_success_rate=1.)
            summary, _ = summarize(raw, run["exclude_first_calls"])
            summary.update(episodes=len(episodes), successes=len(episodes))
        derived.append({"run_id": run["id"], "record": {
            "mode": record["mode"], "label": record["label"],
            "metrics": {key: summary.get(key) for key in METRICS}, "episodes": copy.deepcopy(episodes)}})
    keys = lambda values: [{"task_id": task, "episode": episode} for task, episode in sorted(values)]
    excluded = all_keys - retained
    reasons = [{"run_id": run["id"], "mode": record["mode"],
                "failed": keys({episode_key(e) for e in record["episodes"] if not e["success"]}),
                "missing": keys(all_keys - {episode_key(e) for e in record["episodes"]})} for run, record in rows]
    excluded_text = ", ".join(f"task {t} / episode {e}" for t, e in sorted(excluded)) or "none"
    suite = rows[0][0]['config']['task_suite_name'].replace('libero_', 'LIBERO ').title().replace('Libero', 'LIBERO')
    return {"id": group_id, "title": f"{suite} · {len(retained)} commonly successful cases",
            "run_ids": list(source["run_ids"]),
            "selection": {"kind": "common_success", "source_group": source_id,
                          "keys": ["task_id", "episode"], "retained": keys(retained),
                          "excluded": keys(excluded), "exclusions_by_mode": reasons},
            "derived_records": derived,
            "notes": [f"Only {len(retained)} cases successful in all {len(rows)} modes are included; excluded: {excluded_text}.",
                      "Recomputed from existing records, without a new evaluation. Cases match by task ID / episode; means and p95 use retained calls and control steps.",
                      "Matched case counts are not overall success rates; complete successes and failures remain in the source records.",
                      "Response mean and p95 exclude the first call per episode. Total time retains initial inference waits, and slow within-episode control intervals are not removed.",
                      *[f"Source note: {note}" for note in source.get("notes", [])]]}


def selection_caption(group):
    selection = group.get("selection")
    if not selection:
        return "All recorded episodes, including failures"
    excluded = ", ".join(f"{e['task_id']}/{e['episode']}" for e in selection["excluded"]) or "none"
    return f"{len(selection['retained'])} matched successful cases · Excluded task/episode: {excluded}"


def number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def table(rows, matched=False):
    heading = "Matched cases" if matched else "Original success / total"
    lines = [f"| Device / mode | {heading} | Executed steps | Total time / s | Mean response¹ / ms | Response p95¹ / ms | Control interval p95 / ms | Hold steps |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for _, record in rows:
        s = record["metrics"]
        count = str(s['episodes']) if matched else f"{s['successes']}/{s['episodes']}"
        lines.append(f"| {record['label']} | {count} | {s['executed_steps']} | "
                     f"{number(s['rollout_wall_time_s'])} | {number(s['filtered_calls']['mean_ms'])} | "
                     f"{number(s['filtered_calls']['p95_ms'])} | {number((s['control_intervals'] or {}).get('p95_ms'))} | "
                     f"{number(s['hold_steps'], 0)} |")
    return "\n".join(lines)


def plot_group(rows, path, title, matched=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    labels = [mode_label(record) for _, record in rows]
    colors = [mode_color(run, record) for run, record in rows]
    specs = [("Mean response latency", "ms / chunk", lambda m: m['filtered_calls']['mean_ms']),
             ("Control interval p95", "ms", lambda m: (m['control_intervals'] or {}).get('p95_ms')),
             ("Total task time", "s", lambda m: m['rollout_wall_time_s']),
             ("Task success", "Successes / episodes", lambda m: 100*m['successes']/m['episodes'])]
    if matched:
        specs[-1] = ("Executed steps", "steps", lambda m: m['executed_steps'])
    with plt.rc_context(chart_style()):
        fig, axes = plt.subplots(2, 2, figsize=(13, max(8.8, len(rows)*.8+5)))
        fig.subplots_adjust(left=.12, right=.96, top=.79, bottom=.07, wspace=.47, hspace=.55)
        suite = rows[0][0]["config"]["task_suite_name"].replace("libero_", "LIBERO ").replace("spatial", "Spatial")
        fig.text(.045, .95, f"{suite} · Measured comparison", fontsize=25, weight="bold")
        fig.text(.045, .895, title, fontsize=14, color=MUTED)
        for ax, (heading, unit, get) in zip(axes.flat, specs):
            values = [get(record['metrics']) for _, record in rows]
            maximum = max((value for value in values if value is not None), default=1) or 1
            ax.text(0, 1.17, heading, transform=ax.transAxes, fontsize=19, weight="bold")
            ax.text(0, 1.065, unit, transform=ax.transAxes, fontsize=13, color=MUTED)
            ax.barh(range(len(rows)), [value or 0 for value in values], color=colors, height=.5, zorder=3)
            for index, value in enumerate(values):
                label = "Not recorded" if value is None else f"{value:.2f}"
                if heading == "Executed steps":
                    label = str(value)
                if heading == "Task success":
                    metrics = rows[index][1]['metrics']
                    label = f"{metrics['successes']}/{metrics['episodes']}"
                ax.text((value or 0)+maximum*.035, index, label, va="center",
                        fontsize=15, weight="bold", color=INK)
            ax.set(yticks=range(len(rows)), yticklabels=labels, xlim=(0, maximum*1.32))
            ax.invert_yaxis()
            ax.tick_params(axis='y', length=0, pad=10, labelsize=14)
            ax.tick_params(axis='x', length=0, pad=9, labelsize=12)
            ax.xaxis.set_major_locator(MaxNLocator(3))
            ax.spines[:].set_visible(False)
            ax.set_axisbelow(True)
            ax.grid(axis='x', color=GRID, linewidth=.8)
            if heading == "Task success":
                ax.set_xticks([0, 50, 100], ["0%", "50%", "100%"])
        save_chart(fig, path)
        plt.close(fig)


def replace_block(text, start, end, content):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("Expected one generated results marker pair in README")
    before, rest = text.split(start)
    _, after = rest.split(end)
    return before + start + "\n\n" + content + "\n\n" + end + after


def latest_catalog(catalog):
    """Publish the selected current comparison without unrelated archived runs."""
    selected = next((g for g in catalog['groups'] if g['id'] == catalog['featured_group']), None)
    if selected is None:
        raise ValueError('featured_group does not exist')
    group = copy.deepcopy(selected)
    runs = [copy.deepcopy(run) for run in catalog['runs'] if run['id'] in group['run_ids']]
    suite = runs[0]['config']['task_suite_name'].replace('libero_', 'LIBERO ').replace('spatial', 'Spatial')
    group['title'] = f'{suite} · Measured comparison'
    from scripts.libero.benchmark_text import english_note
    group['notes'] = [english_note(note)
                      for note in group.get('notes', [])
                      if not re.search(r'\d{4}-\d{2}-\d{2}|历史分组', note)]
    return {'schema_version': catalog['schema_version'], 'featured_group': group['id'],
            'groups': [group], 'runs': runs}


def build(catalog):
    catalog = latest_catalog(catalog)
    (REPORTS/'latest.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    all_rows = []
    page = ["# Measured results", "", "Results come from completed runs. Tables and figures share one appendable data catalog. Async maps to the CLI name `replace`.", "",
            "<BenchmarkDashboard />", "", "## Static comparison and downloads", "",
            "¹ Mean and p95 exclude the first N calls per episode; N is listed in the source table. Response latency spans a policy call through receipt of a complete action chunk. Remote calls include preprocessing, transport and server inference; values are not per-action latency. `—` means not recorded.", "",
            "[Download current JSON](../../reports/evaluation/latest.json) · [Download summary CSV](../../reports/evaluation/summary.csv)", ""]
    featured = None
    for group in catalog['groups']:
        rows = group_rows(catalog, group)
        matched = bool(group.get('selection'))
        caption = selection_caption(group)
        image_name = group['id']
        plot_group(rows, ROOT / f"assets/benchmarks/{image_name}", caption, matched)
        stage_chart = plot_stage_timings(rows, ROOT / f"assets/benchmarks/{image_name}-stages", caption)
        page += ['<details class="benchmark-details"><summary>Full figures and records</summary>', "", f"## {group['title']}", "", caption, "", table(rows, matched), "",
                 f"![{group['title']} four metrics](../../assets/benchmarks/{image_name}.svg)", ""]
        page += [f"- {note}" for note in group.get('notes', [])] + [""]
        runs = [r for r in catalog['runs'] if r['id'] in group['run_ids']]
        mismatches = [key for key in CONFIG_KEYS if len({json.dumps(r['config'][key]) for r in runs}) > 1]
        if mismatches:
            page += ["**Configuration differences: " + ", ".join(mismatches) + ". Shown side by side, not as a controlled comparison.**", ""]
        page += ["### Scheduling and calls", "",
                 "| Mode | Calls: all / filtered | Mean first response / ms | Post-bootstrap blocking / s | Inference / env.step overlap | drain / s | Command-change L2 p95 |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for _, record in rows:
            m=record['metrics']; overlap=m['env_overlap_fraction_of_inference']
            page += [f"| {record['label']} | {m['all_calls']['count']} / {m['filtered_calls']['count']} | "
                     f"{number(m['first_call_per_episode']['mean_ms'])} | {number(m['blocking_wait_after_bootstrap_s'],3)} | "
                     f"{number(100*overlap if overlap is not None else None)} | {number(m['worker_drain_after_episode_s'],3)} | "
                     f"{number((m['arm_action_changes'] or {}).get('p95_action_l2'),3)} |"]
        page += ["", "Overlap is a percentage. L2 measures adjacent six-dimensional relative commands with mixed translation/rotation units; it is not physical jerk.", "",
                 "### Latency breakdown", ""]
        if stage_chart:
            page += [f"![Complete local calls and remote latency stages](../../assets/benchmarks/{image_name}-stages.svg)", "",
                     f"[Download SVG](../../assets/benchmarks/{image_name}-stages.svg) · [Download PNG](../../assets/benchmarks/{image_name}-stages.png)", "",
                     "Local bars show complete calls. Remote stages use the same filtered samples and their means sum to mean response latency. p95 is computed separately. See [Data maintenance](./benchmark-data.md)。", ""]
        page += ["| Remote mode | Orin preprocessing | Encoding | Thor decode/queue | Thor inference | HTTP/transport | Other overhead |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for _, record in rows:
            breakdown = latency_breakdown(record)
            if breakdown:
                page += [f"| {record['label']} | " + ' | '.join(number(value) for value in breakdown['values']) + ' |']
        page += ["", "Units: ms. HTTP/transport includes receive waits and system overhead. No breakdown is inferred from incomplete or mismatched samples.", "", "### Source runs", ""]
        page += ["| Source run | Configuration | Initial calls excluded / episode |", "| --- | --- | ---: |"]
        for run in [r for r in catalog['runs'] if r['id'] in group['run_ids']]:
            c=run['config']
            source_label = f"{run['hardware']['device_name'].title()} " + ('local' if run['kind'] == 'local' else 'Remote inference')
            page += [f"| {source_label} | {c['task_suite_name']} / {c['precision']} / seed {c['seed']} / chunk {c['chunk_size']} | {run['exclude_first_calls']} |"]
        page += ["", "### Per-task results", "",
                 "| Mode | task ID | episode | Success | Steps | Task time / s | Hold steps |",
                 "| --- | ---: | ---: | --- | ---: | ---: | ---: |"]
        for run, record in rows:
            s=record['metrics']
            all_rows.append({'group':group['id'], 'run_id':run['id'], 'mode':record['mode'], 'label':record['label'],
                'selection': 'common_success' if matched else 'all_episodes',
                'source_group': group.get('selection', {}).get('source_group', group['id']),
                'suite':run['config']['task_suite_name'], 'precision':run['config']['precision'], 'seed':run['config']['seed'],
                'episodes':s['episodes'], 'successes':s['successes'], 'executed_steps':s['executed_steps'],
                'rollout_wall_time_s':s['rollout_wall_time_s'], 'all_calls':s['all_calls']['count'],
                'filtered_call_count':s['filtered_calls']['count'], 'filtered_call_mean_ms':s['filtered_calls']['mean_ms'],
                'filtered_call_p95_ms':s['filtered_calls']['p95_ms'], 'control_interval_p95_ms':(s['control_intervals'] or {}).get('p95_ms'),
                'hold_steps':s['hold_steps'], 'bootstrap_wait_s':s['bootstrap_wait_s'],
                'blocking_wait_after_bootstrap_s':s['blocking_wait_after_bootstrap_s'],
                'worker_drain_s':s['worker_drain_after_episode_s']})
            for e in record['episodes']:
                page += [f"| {record['label']} | {e['task_id']} | {e['episode']} | {'Yes' if e['success'] else 'No'} | {e['steps']} | {number(e['wall_s'])} | {number(e['hold_steps'],0)} |"]
        page += ["", "</details>", ""]
        if group['id'] == catalog['featured_group']:
            selection_note = (caption + ". Recomputed from existing records, without rerunning evaluation. Matched case counts are not overall success rates.\n\n"
                              if matched else caption + "。\n\n")
            featured = (f"**{group['title']}**\n\n" + selection_note + table(rows, matched) + "\n\n¹ See the data page for initial-call filtering. `—` means not recorded. Response latency is per action chunk and includes preprocessing, transport and server inference in remote mode. Total time retains initial inference waits.\n\n"
                        +f"![Measured metric comparison](assets/benchmarks/{image_name}.svg)\n\n"
                        +"[Detailed results and methodology](docs-site/guide/benchmark-results.md) · [JSON data](reports/evaluation/latest.json) · [CSV summary](reports/evaluation/summary.csv)")
            if stage_chart:
                featured += ("\n\n**Latency breakdown**\n\n"
                             + f"![Local and remote inference latency breakdown](assets/benchmarks/{image_name}-stages.svg)\n\n"
                             + "Local bars show complete calls; remote bars show stage means that sum to mean response latency. HTTP/transport includes receive waits and system overhead.\n\n"
                             + f"[Download SVG](assets/benchmarks/{image_name}-stages.svg) · [Download PNG](assets/benchmarks/{image_name}-stages.png)")
    if featured is None:
        raise ValueError("featured_group does not exist")
    page += ["## Methodology and updates", "", "See [data maintenance](./benchmark-data.md). Pages and downloads publish only the current comparison, including per-task results. JSON retains source run IDs and checksums; rebuilding the website does not require raw files.", ""]
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
    select = sub.add_parser('select-common-success', help='Recompute matched successful episodes from existing raw records')
    select.add_argument('--source-group', required=True)
    select.add_argument('--group', required=True)
    select.add_argument('--featured', action='store_true')
    sub.add_parser('build',help='Regenerate figures, tables and README from the published catalog')
    args=parser.parse_args()
    catalog=json.loads(CATALOG.read_text()) if CATALOG.exists() else {'schema_version':1,'groups':[],'runs':[]}
    if args.command=='add':
        add_run(catalog,import_run(args.run_dir),args.group,args.title)
        write_json(CATALOG,catalog)
        print(f'Imported {args.run_dir.name}; run build to update documentation.')
    elif args.command == 'select-common-success':
        group = common_success_group(catalog, args.source_group, args.group)
        existing = next((g for g in catalog['groups'] if g['id'] == args.group), None)
        if existing is not None:
            if not existing.get('selection') or existing['selection']['source_group'] != args.source_group:
                raise ValueError('Cannot overwrite an unrelated group')
            catalog['groups'][catalog['groups'].index(existing)] = group
        else:
            catalog['groups'].insert(0, group)
        if args.featured:
            catalog['featured_group'] = args.group
        write_json(CATALOG, catalog)
        print(selection_caption(group) + '; recomputed from existing files, no evaluation run.')
    else:
        build(catalog); print('Updated benchmark figures, CSV, README and documentation.')


if __name__=='__main__':
    main()
