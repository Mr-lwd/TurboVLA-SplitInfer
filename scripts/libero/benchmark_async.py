"""Isolated synchronous/async-replacement/async-blending LIBERO comparison."""

import argparse
import csv
from dataclasses import asdict, fields
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "third_party/vla_adapter")]

from scripts.libero.benchmark_local import (
    REMOTE_BYTES, REMOTE_MEMORY, REMOTE_STAGES, device_label, distribution,
    expand_path, hardware_info, load_settings, local_path, write_json,
)
from turbovla.evaluation.async_rollout import MODES, overlap_seconds, run_episode, save_realtime_video


def summarize_episodes(episodes, exclude_first_calls=1):
    if exclude_first_calls < 0:
        raise ValueError("exclude_first_calls must be nonnegative")
    calls = [c for e in episodes for c in e["inference_timings"]]
    filtered = [c for e in episodes for c in e["inference_timings"][exclude_first_calls:]]
    steps = [s for e in episodes for s in e["step_timings"]]
    wall = sum(e["rollout_wall_time_s"] for e in episodes)
    intervals = [b["action_start_s"] - a["action_start_s"] for e in episodes
                 for a, b in zip(e["step_timings"], e["step_timings"][1:])]
    overlap = sum(overlap_seconds(e["inference_timings"], e["step_timings"]) for e in episodes)
    in_rollout = sum(max(0., min(c["end_s"], e["rollout_wall_time_s"]) - c["start_s"])
                     for e in episodes for c in e["inference_timings"])
    groups = {"all_calls": calls, "filtered_calls": filtered,
              "first_call_per_episode": [e["inference_timings"][0] for e in episodes if e["inference_timings"]]}
    def remote_metric(key, unit="ms", scale=1000):
        result = {}
        for name, group in groups.items():
            values = [c["remote"][key] for c in group if c.get("remote", {}).get(key) is not None]
            result[name] = {**distribution(values, unit, scale), "missing_count": len(group) - len(values)}
        return result
    return {
        "episodes": len(episodes), "successes": sum(e["success"] for e in episodes),
        "success_rate": sum(e["success"] for e in episodes) / len(episodes) if episodes else None,
        "executed_steps": len(steps), "rollout_wall_time_s": wall,
        "executed_steps_per_wall_second": len(steps) / wall if wall else None,
        "all_calls": distribution([c["duration_s"] for c in calls]),
        "filtered_calls": distribution([c["duration_s"] for c in filtered]),
        "first_call_per_episode": distribution([e["inference_timings"][0]["duration_s"] for e in episodes if e["inference_timings"]]),
        "filter": f"exclude first {exclude_first_calls} calls per episode from filtered_calls only",
        "policy_calls_without_injected_delay": distribution([c["policy_duration_s"] for c in calls]),
        "control_intervals": distribution(intervals),
        "env_steps": distribution([s["env_step_s"] for s in steps]),
        "control_lateness": distribution([s["control_lateness_s"] for s in steps]),
        "bootstrap_wait_s": sum(w["end_s"] - w["start_s"] for e in episodes for w in e["blocking_waits"] if w["kind"] == "bootstrap"),
        "blocking_wait_after_bootstrap_s": sum(w["end_s"] - w["start_s"] for e in episodes for w in e["blocking_waits"] if w["kind"] != "bootstrap"),
        "hold_steps": sum(s["hold"] for s in steps),
        "expired_chunks": sum(c["expired"] for c in calls),
        "applied_chunks": sum(c["applied"] for c in calls),
        "unused_at_episode_end": sum(c["reason"] == "episode_ended" for c in calls),
        "discarded_prefix_actions": sum(c["discarded_prefix_actions"] for c in calls),
        "blended_action_slots": sum(c["blended_steps"] for c in calls),
        "inference_inside_rollout_s": in_rollout,
        "inference_overlapped_with_env_step_s": overlap,
        "env_overlap_fraction_of_inference": overlap / in_rollout if in_rollout else None,
        "worker_drain_after_episode_s": sum(e["drain_wall_time_s"] for e in episodes),
        "oldest_observation_age": distribution([s["oldest_observation_age_steps"] for s in steps if s["oldest_observation_age_steps"] is not None], "steps", 1),
        "arm_action_changes": distribution([s["arm_action_change_l2"] for s in steps if s["arm_action_change_l2"] is not None], "action_l2", 1),
        "gripper_switches": sum(s["gripper_changed"] for s in steps),
        "remote_stage_timings": {key: remote_metric(key) for key in REMOTE_STAGES},
        "remote_payload": {key: remote_metric(key, "bytes", 1) for key in REMOTE_BYTES},
        "remote_memory": {key: {"max_bytes": max((c["remote"][key] for c in calls
            if c.get("remote", {}).get(key) is not None), default=None)} for key in REMOTE_MEMORY},
        "remote_memory_scope": "server process lifetime PyTorch allocator peak; not this episode alone or total shared RAM",
        "remote_stage_note": "stages are nested, not additive; transport_overhead includes HTTP/response overhead, not pure wire latency",
        "timing_note": "inference overlaps control; do not subtract summed inference from wall time. Pending calls drained after episode are recorded separately.",
        "action_change_note": "L2 of consecutive six-dimensional relative arm commands in mixed action units; not physical acceleration/jerk",
    }


def write_csv(path, rows):
    columns = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)


def export_mode(root, mode, episodes, experiment, exclude_first_calls):
    prefix = root / f"{root.name}_{mode}"
    summary = summarize_episodes(episodes, exclude_first_calls)
    write_json(prefix.with_name(prefix.name + "_summary.json"), summary)
    write_json(prefix.with_suffix(".json"), {"mode": mode, "experiment": experiment, "episodes": episodes})
    write_csv(prefix.with_name(prefix.name + "_calls.csv"), [
        {"task_id": e["task_id"], "episode": e["episode"], "call_index": index,
         "included_in_filtered": index >= exclude_first_calls, **c, **c.get("remote", {})}
        for e in episodes for index, c in enumerate(e["inference_timings"])])
    write_csv(prefix.with_name(prefix.name + "_steps.csv"), [
        {"task_id": e["task_id"], "episode": e["episode"], "action": action, **step}
        for e in episodes for action, step in zip(e["executed_actions"], e["step_timings"])])
    return summary


def main():
    import yaml
    from vla_adapter import rollout

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", default="experiments/libero/configs/async_benchmark.yaml")
    parser.add_argument("--modes", nargs="+", choices=MODES)
    parser.add_argument("--replan_every_steps", type=int)
    parser.add_argument("--blend_steps", type=int)
    parser.add_argument("--control_hz", type=float)
    parser.add_argument("--extra_delay_s", type=float)
    parser.add_argument("--output_root")
    parser.add_argument("--preflight", action="store_true")
    args, rest = parser.parse_known_args()
    os.chdir(ROOT)
    config_path = expand_path(args.config)
    config = yaml.safe_load(config_path.read_text())
    if not isinstance(config, dict) or set(config) != {"base_config", "evaluation", "experiment"}:
        parser.error("Expected base_config, evaluation and experiment sections")
    if not isinstance(config["base_config"], str) or any(not isinstance(config[k], dict) for k in ("evaluation", "experiment")):
        parser.error("base_config must be a path; evaluation and experiment must be mappings")
    base = load_settings(expand_path(config["base_config"]), rollout.GenerateConfig, split=True)
    experiment = dict(config["experiment"])
    expected = {"modes", "replan_every_steps", "blend_steps", "control_hz", "extra_delay_s", "output_root"}
    if set(experiment) != expected:
        parser.error(f"experiment requires {sorted(expected)}")
    for key in expected:
        if getattr(args, key) is not None:
            experiment[key] = getattr(args, key)
    if not isinstance(experiment["output_root"], str) or not experiment["output_root"].strip():
        parser.error("output_root must be a nonempty path")
    modes = experiment["modes"]
    if not isinstance(modes, list) or not modes or any(m not in MODES for m in modes) or len(set(modes)) != len(modes):
        parser.error("modes must be a nonempty unique list of sync/replace/blend")
    for key in ("replan_every_steps", "blend_steps"):
        if type(experiment[key]) is not int or experiment[key] < 1:
            parser.error(f"{key} must be a positive integer")
    for key in ("control_hz", "extra_delay_s"):
        if type(experiment[key]) not in (int, float) or not float('-inf') < experiment[key] < float('inf'):
            parser.error(f"{key} must be finite numeric")
    if experiment["control_hz"] <= 0 or experiment["extra_delay_s"] < 0:
        parser.error("control_hz must be positive; extra_delay_s must be nonnegative")
    evaluation = {**base["evaluation"], **config["evaluation"]}
    known = {field.name: type(field.default) for field in fields(rollout.GenerateConfig)}
    defaults = []
    for key, value in evaluation.items():
        if key not in known or (type(value) is not known[key] and not (known[key] is float and type(value) is int)):
            parser.error(f"Unknown evaluation key or invalid YAML type: {key}")
        defaults.extend([f"--{key}", str(value).lower() if isinstance(value, bool) else str(value)])
    if os.environ.get("THOR_URL"):
        defaults += ["--remote_policy_url", os.environ["THOR_URL"]]
    cfg = rollout.parse_args([*defaults, *rest])
    if not cfg.remote_policy_url or cfg.control_mode != "relative" or cfg.dry_run_model_load:
        parser.error("This isolated experiment requires a remote policy, relative control and real rollouts")
    if cfg.chunk_size != cfg.num_open_loop_steps or cfg.num_trials_per_task < 1:
        parser.error("Require chunk_size == num_open_loop_steps and trials >= 1")
    if experiment["replan_every_steps"] >= cfg.chunk_size or experiment["blend_steps"] > cfg.chunk_size:
        parser.error("Require replan_every_steps < chunk_size and blend_steps <= chunk_size")
    if cfg.task_suite_name not in rollout.LIBERO_SUITES:
        parser.error("Unknown LIBERO suite")
    if cfg.result_json_path or cfg.log_path or cfg.video_out_path != "outputs/evaluation":
        parser.error("Use --output_root for this experiment's separate output files")
    roots = base["paths"]["libero_root"]
    cfg.libero_root = local_path(cfg.libero_root, "LIBERO_ROOT", roots if isinstance(roots, list) else [roots], directory=True)
    libero_paths = {key: str(expand_path(value, cfg.libero_root)) for key, value in base["libero_paths"].items()}
    for key, value in libero_paths.items():
        if key != "datasets" and not Path(value).is_dir():
            raise FileNotFoundError(value)
    os.environ["MUJOCO_GL"] = cfg.mujoco_gl
    os.environ["PYOPENGL_PLATFORM"] = cfg.pyopengl_platform
    import torch
    from turbovla.split.client import RemoteTurboVLAPolicy
    from turbovla.evaluation.suite_policy import set_seed_everywhere

    metadata = hardware_info(torch)
    with RemoteTurboVLAPolicy(cfg.remote_policy_url, timeout=cfg.remote_timeout_s, precision=cfg.precision,
                             chunk_size=cfg.chunk_size, compression=cfg.remote_compression,
                             keepalive=cfg.remote_keepalive) as policy:
        if policy.server_info["stats_key"] != cfg.stats_key:
            raise ValueError("Server stats_key mismatch")
        server_name = device_label(policy.server_info.get("gpu_name", ""), "", "server")
        stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
        root = expand_path(experiment["output_root"]) / f"{metadata['device_name']}_to_{server_name}_async_{cfg.task_suite_name}_{stamp}"
        metadata.update(config=asdict(cfg), experiment=experiment, source_config=config,
                        base_config=base, resolved_libero_paths=libero_paths,
                        remote_server=policy.server_info, compression=policy.compression,
                        alignment="executed LIBERO control steps since observation; never elapsed network wall-time / period",
                        experiment_type="inference-only scheduling heuristic; no retraining, no delay-conditioned model",
                        status="running")
        print(json.dumps({"output": str(root), "experiment": experiment, "compression": policy.compression}, indent=2), flush=True)
        if args.preflight:
            return
        root.mkdir(parents=True, exist_ok=False)
        cfg.log_path = str(root / f"{root.name}.log")
        metadata["config"] = asdict(cfg)
        rollout._setup_logging(cfg)
        path_dir = root / "libero_config"
        path_dir.mkdir()
        (path_dir / "config.yaml").write_text(yaml.safe_dump(libero_paths))
        os.environ["LIBERO_CONFIG_PATH"] = str(path_dir)
        rollout._ensure_libero_import_path(cfg)
        from libero.libero import benchmark

        suite = benchmark.get_benchmark_dict()[cfg.task_suite_name]()
        task_ids = [int(v.strip()) for v in cfg.task_ids.split(",") if v.strip()] if cfg.task_ids else list(range(
            min(suite.n_tasks, cfg.max_tasks) if cfg.max_tasks > 0 else suite.n_tasks))
        if not task_ids or len(set(task_ids)) != len(task_ids) or any(t < 0 or t >= suite.n_tasks for t in task_ids):
            raise ValueError("Invalid or duplicate task IDs")
        metadata["requested_task_ids"] = task_ids
        meta_path = root / f"{root.name}_metadata.json"
        write_json(meta_path, metadata)
        outcomes = {mode: [] for mode in modes}
        order_rng = random.Random(cfg.seed)
        order = []
        start = time.perf_counter()
        try:
            for task_id in task_ids:
                task = suite.get_task(task_id)
                states = suite.get_task_init_states(task_id)
                if cfg.num_trials_per_task > len(states):
                    raise ValueError("Not enough initial states")
                for episode_index in range(cfg.num_trials_per_task):
                    mode_order = list(modes)
                    order_rng.shuffle(mode_order)
                    for mode in mode_order:
                        set_seed_everywhere(cfg.seed)
                        env, instruction = rollout._make_libero_env(task, cfg)
                        try:
                            simulation_hz = getattr(getattr(env, "env", env), "control_freq", None)
                            episode = run_episode(cfg, env, policy, instruction, states[episode_index], mode,
                                **{key: experiment[key] for key in ("replan_every_steps", "blend_steps", "control_hz", "extra_delay_s")})
                        finally:
                            env.close()
                        record = {"task_id": task_id, "episode": episode_index, "instruction": instruction,
                                  "simulation_control_hz": simulation_hz, **episode.record()}
                        if cfg.save_video:
                            video = root / mode / "videos" / f"task{task_id:02d}_ep{episode_index:03d}_{'success' if episode.success else 'failure'}.mp4"
                            rollout._save_video(video, episode.frames[:-1])
                            record["video_path"] = str(video)
                            if cfg.save_realtime_video:
                                realtime = video.with_name(video.stem + "_realtime.mp4")
                                record["realtime_video_path"] = str(realtime)
                                record["realtime_video_duration_s"] = save_realtime_video(realtime, episode, mode)
                        outcomes[mode].append(record)
                        order.append({"task_id": task_id, "episode": episode_index, "mode": mode})
                        export_mode(root, mode, outcomes[mode], experiment, base["benchmark"]["exclude_first_calls"])
                        logging.info("mode=%s task=%d episode=%d success=%s steps=%d calls=%d holds=%d wall=%.3fs",
                                     mode, task_id, episode_index, episode.success, len(episode.actions), len(episode.calls),
                                     sum(s["hold"] for s in episode.steps), episode.rollout_wall_time_s)
            comparison = {mode: summarize_episodes(outcomes[mode], base["benchmark"]["exclude_first_calls"]) for mode in modes}
            write_json(root / f"{root.name}_comparison.json", comparison)
            write_csv(root / f"{root.name}_comparison.csv", [{"mode": mode, **result} for mode, result in comparison.items()])
            metadata["status"] = "completed"
            print(json.dumps(comparison, indent=2), flush=True)
        except BaseException as exc:
            metadata.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            metadata.update(evaluation_order=order, experiment_wall_time_s=time.perf_counter() - start)
            write_json(meta_path, metadata)
        print(f"Saved async comparison: {root}")


if __name__ == "__main__":
    main()
