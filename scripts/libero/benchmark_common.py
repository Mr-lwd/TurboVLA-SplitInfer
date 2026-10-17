"""Shared configuration, hardware metadata and report helpers for LIBERO benchmarks.

summarize/write_reports handle the original sequential result format (local and
historical remote results). Async overlap-aware summaries live in benchmark_async.
"""

from dataclasses import fields
import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "experiments/libero/configs/local_benchmark.yaml"
PATH_ENV = {"ckpt_path": "CKPT_PATH", "libero_root": "LIBERO_ROOT",
            "dinov3_path": "DINOV3_PATH", "bert_path": "BERT_PATH", "stats_path": "STATS_PATH"}
LIBERO_KEYS = {"benchmark_root", "bddl_files", "init_states", "assets", "datasets"}
REMOTE_STAGES = ("client_preprocess_s", "client_encode_s", "round_trip_s", "server_decode_s",
                 "server_queue_s", "server_inference_s", "server_total_s", "transport_overhead_s",
                 "client_request_send_s", "client_response_wait_s", "client_response_read_s", "server_receive_s")
REMOTE_BYTES = ("request_bytes", "uncompressed_tensor_bytes")
REMOTE_MEMORY = ("server_cuda_peak_allocated_bytes", "server_cuda_peak_reserved_bytes")
BASE_COLUMNS = ["task_id", "episode", "call_index", "step", "duration_s", "duration_ms", "included_in_filtered"]
STEP_COLUMNS = ["task_id", "episode", "step", "action_start_s", "action_end_s",
                "env_step_s", "control_interval_s", "hold"]


def expand_path(value, libero_root=None):
    value = value.replace("${REPO_ROOT}", str(REPO_ROOT))
    if libero_root is not None:
        value = value.replace("${libero_root}", str(libero_root))
    value = os.path.expandvars(value)
    if "$" in value:
        raise ValueError(f"Unresolved variable in path: {value}")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


def load_settings(path, config_type, *, remote=False):
    import yaml

    with path.open(encoding="utf-8") as stream:
        settings = yaml.safe_load(stream)
    sections = {"paths", "libero_paths", "benchmark", "evaluation"}
    if remote:
        sections.add("experiment")
        if isinstance(settings, dict) and "base_config" in settings:
            raise ValueError("base_config is no longer supported; copy the standalone async_benchmark.yaml "
                             "and configure paths/libero_paths/benchmark/evaluation/experiment there")
    if not isinstance(settings, dict) or set(settings) != sections:
        raise ValueError(f"Config requires exactly these sections: {sorted(sections)}")
    for section in sections:
        if not isinstance(settings[section], dict):
            raise ValueError(f"{section} must be a mapping")
    for section, keys in (("paths", {"libero_root"} if remote else set(PATH_ENV)), ("libero_paths", LIBERO_KEYS),
                          ("benchmark", {"output_root", "exclude_first_calls"})):
        if set(settings[section]) != keys:
            raise ValueError(f"{section} requires exactly these keys: {sorted(keys)}")
    for key, value in settings["paths"].items():
        choices = value if isinstance(value, list) else [value]
        if not choices or any(not isinstance(item, str) or not item.strip() for item in choices):
            raise ValueError(f"paths.{key} must be a path or nonempty list of paths")
    for key, value in settings["libero_paths"].items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"libero_paths.{key} must be a path")
    benchmark = settings["benchmark"]
    if not isinstance(benchmark["output_root"], str) or not benchmark["output_root"].strip():
        raise ValueError("benchmark.output_root must be a path")
    if type(benchmark["exclude_first_calls"]) is not int or benchmark["exclude_first_calls"] < 0:
        raise ValueError("benchmark.exclude_first_calls must be a nonnegative integer")
    defaults = {field.name: field.default for field in fields(config_type)}
    forbidden = set(PATH_ENV) | {"result_json_path", "log_path", "video_out_path", "remote_policy_url", "dry_run_model_load"}
    if remote:
        forbidden.remove("remote_policy_url")
    for key, value in settings["evaluation"].items():
        if key not in defaults or key in forbidden:
            raise ValueError(f"Unsupported evaluation option: {key}; configure paths/output in their own sections")
        expected = type(defaults[key])
        if type(value) is not expected and not (expected is float and type(value) is int):
            raise ValueError(f"evaluation.{key} must be {expected.__name__}, got {type(value).__name__}")
    return settings


def device_label(gpu_name, board_name, hostname):
    # Hardware takes priority over a user-assigned hostname.
    hardware = f"{gpu_name} {board_name}".lower()
    for name in ("thor", "orin"):
        if name in hardware:
            return name
    return re.sub(r"[^a-z0-9_-]+", "_", gpu_name.lower() or hostname.lower()).strip("_") or "unknown"


def distribution(values, unit="ms", scale=1000):
    values = sorted(values)
    if not values:
        return {"count": 0, **{f"{key}_{unit}": None for key in ("mean", "median", "p95", "min", "max")}}
    position = (len(values) - 1) * 0.95
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return {"count": len(values), f"mean_{unit}": statistics.mean(values) * scale,
            f"median_{unit}": statistics.median(values) * scale,
            f"p95_{unit}": (values[lo] + (values[hi] - values[lo]) * (position - lo)) * scale,
            f"min_{unit}": values[0] * scale, f"max_{unit}": values[-1] * scale}


def control_step_rows(result):
    """Validate recorded control timestamps; never infer them from call/video timing."""
    rows = []
    for task in result["tasks"]:
        for episode in task["episode_results"]:
            steps = episode.get("step_timings")
            if steps is None:  # Historical results did not record control steps.
                continue
            if not isinstance(steps, list) or len(steps) != episode["executed_steps"]:
                raise ValueError("Control-step count mismatch")
            previous = None
            for index, step in enumerate(steps):
                start, end, duration = (step[key] for key in ("action_start_s", "action_end_s", "env_step_s"))
                if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
                       for v in (start, end, duration)):
                    raise ValueError("Invalid control-step timestamp")
                if (step["step"] != index or end < start or
                    end > episode["rollout_wall_time_s"] + 1e-7 or
                    (previous is not None and start < previous["action_end_s"]) or
                    not math.isclose(end - start, duration, rel_tol=1e-7, abs_tol=1e-7) or
                    type(step["hold"]) is not bool):
                    raise ValueError("Inconsistent control-step timing")
                rows.append({"task_id": task["task_id"], "episode": episode["episode"],
                             **{key: step[key] for key in ("step", "action_start_s", "action_end_s", "env_step_s", "hold")},
                             "control_interval_s": start - previous["action_start_s"] if previous is not None else None})
                previous = step
    return rows


def summarize(result, exclude_first_calls):
    if exclude_first_calls < 0:
        raise ValueError("exclude_first_calls must be nonnegative")
    backend = result.get("policy_backend")
    if backend not in {"local", "remote"}:
        raise ValueError("Expected a local or remote evaluation result")
    rows, episodes = [], []
    for task in result["tasks"]:
        for episode in task["episode_results"]:
            episodes.append(episode)
            for index, timing in enumerate(episode["inference_timings"]):
                rows.append({"task_id": task["task_id"], "episode": episode["episode"],
                             "call_index": index, "step": timing["step"],
                             "duration_s": timing["duration_s"],
                             "duration_ms": timing["duration_s"] * 1000,
                             "included_in_filtered": index >= exclude_first_calls})
                if not math.isfinite(timing["duration_s"]) or timing["duration_s"] < 0:
                    raise ValueError("Invalid inference duration")
                if backend == "remote":
                    remote = timing.get("remote")
                    if not isinstance(remote, dict):
                        raise ValueError("Remote call is missing remote timing data")
                    rows[-1]["request_id"] = remote.get("request_id")
                    rows[-1]["compression"] = remote.get("compression")
                    rows[-1]["connection_reused"] = remote.get("connection_reused")
                    for key in (*REMOTE_STAGES, *REMOTE_BYTES, *REMOTE_MEMORY):
                        value = remote.get(key)
                        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                            raise ValueError(f"Invalid remote metric: {key}")
                        rows[-1][key] = value
    all_calls = [row["duration_s"] for row in rows]
    filtered = [row["duration_s"] for row in rows if row["included_in_filtered"]]
    first_calls = [row["duration_s"] for row in rows if row["call_index"] == 0]
    wall = sum(ep["rollout_wall_time_s"] for ep in episodes)
    inference = sum(all_calls)
    steps = sum(ep["executed_steps"] for ep in episodes)
    step_rows = control_step_rows(result)
    recorded_episodes = sum(ep.get("step_timings") is not None for ep in episodes)
    complete_steps = bool(episodes) and recorded_episodes == len(episodes)
    chunk = result.get("chunk_size") or (result.get("remote_server") or {}).get("chunk_size")
    if not isinstance(chunk, int) or chunk <= 0:
        raise ValueError("Result must record a positive model chunk_size")
    summary = {
        "scope": "complete synchronous policy call: preprocessing, inference, transfers and action decoding; not GPU-only",
        "filter": f"exclude first {exclude_first_calls} calls of EACH episode from filtered statistics only; no extra warmup calls",
        "percentile_method": "linear interpolation",
        "all_calls": distribution(all_calls),
        "first_call_per_episode": distribution(first_calls),
        "filtered_calls": distribution(filtered),
        "filtered_amortized_ms_per_predicted_action": statistics.mean(filtered) * 1000 / chunk if filtered else None,
        "filtered_predicted_actions_per_inference_second": len(filtered) * chunk / sum(filtered) if sum(filtered) > 0 else None,
        "amortization_note": "chunk latency divided by model chunk size; actions become available together, not at this interval",
        "chunk_size": chunk, "num_open_loop_steps": result["num_open_loop_steps"],
        "total_episodes": result["total_episodes"], "total_successes": result["total_successes"],
        "overall_success_rate": result["overall_success_rate"],
        "executed_steps": steps, "rollout_wall_time_s": wall,
        "control_intervals": distribution([r["control_interval_s"] for r in step_rows
                                            if r["control_interval_s"] is not None]) if complete_steps else None,
        "env_steps": distribution([r["env_step_s"] for r in step_rows]) if complete_steps else None,
        "hold_steps": sum(r["hold"] for r in step_rows) if complete_steps else None,
        "control_timing_episodes": {"recorded": recorded_episodes, "total": len(episodes)},
        "control_interval_scope": "adjacent env.step start times within each episode, pooled before percentiles; "
                                  "no first-call filtering, no cross-episode intervals; initial inference before the first "
                                  "action is excluded; no wall-clock rate limiter in this runner; "
                                  "null if any episode lacks step timings",
        "hold_scope": "dummy-action fallback when the synchronous policy returns an empty chunk; excludes settling steps",
        "inference_total_s": inference, "non_inference_rollout_s": wall - inference,
        "non_inference_scope": "simulation, rendering, image preparation and Python overhead; not environment stepping alone",
        "inference_fraction_of_rollout": inference / wall if wall else None,
        "executed_steps_per_rollout_second": steps / wall if wall else None,
        "rollout_scope": result["timing_scope"],
        "policy_backend": backend,
    }
    if backend == "remote":
        summary["scope"] = "complete client policy call including preprocessing, encoding, HTTP round trip, response validation; not server-only"
        groups = {"all_calls": rows, "first_call_per_episode": [r for r in rows if r["call_index"] == 0],
                  "filtered_calls": [r for r in rows if r["included_in_filtered"]]}
        def metric_groups(key, unit="ms", scale=1000):
            output = {}
            for name, group in groups.items():
                values = [r[key] for r in group if r[key] is not None]
                output[name] = {**distribution(values, unit, scale), "missing_count": len(group) - len(values),
                                "total": sum(values) if values else None, "total_unit": "s" if unit == "ms" else unit}
            return output
        summary["remote_stage_timings"] = {key: metric_groups(key) for key in REMOTE_STAGES}
        summary["remote_payload"] = {key: metric_groups(key, "bytes", 1) for key in REMOTE_BYTES}
        summary["remote_memory"] = {
            key: {"max_bytes": max((r[key] for r in rows if r[key] is not None), default=None),
                  "missing_count": sum(r[key] is None for r in rows)} for key in REMOTE_MEMORY}
        summary["remote_memory_scope"] = "server process lifetime PyTorch allocator peak, including model load/warmup and possibly earlier clients; not this rollout alone or total shared RAM"
        summary["remote_stage_note"] = "round_trip includes server_total, which includes decode/queue/inference; do not add overlapping stages. transport_overhead includes HTTP and response handling, not pure network latency"
        summary["remote_payload_note"] = "request_bytes is the HTTP body including protocol header and compressed tensors; excludes HTTP/TCP headers"
        summary["remote_transport"] = {
            "codecs_used": sorted({r["compression"] for r in rows if r["compression"] is not None}),
            "connection_reused_count": sum(r["connection_reused"] is True for r in rows),
            "connection_reuse_missing_count": sum(r["connection_reused"] is None for r in rows),
        }
    return summary, rows


def write_reports(prefix, summary, rows, step_rows=None):
    write_json(prefix.with_name(prefix.name + "_summary.json"), summary)
    columns = BASE_COLUMNS + (["request_id", "compression", "connection_reused", *REMOTE_STAGES, *REMOTE_BYTES, *REMOTE_MEMORY]
                              if summary["policy_backend"] == "remote" else [])
    with prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    if step_rows is not None:
        with prefix.with_name(prefix.name + "_steps.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=STEP_COLUMNS)
            writer.writeheader()
            writer.writerows(step_rows)


def command_output(command):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5, cwd=REPO_ROOT)
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def hardware_info(torch):
    board_path = Path("/proc/device-tree/model")
    board = board_path.read_text().strip("\x00\n") if board_path.exists() else ""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; activate the device's TurboVLA environment")
    gpu = torch.cuda.get_device_name()
    versions = {}
    for package in ("transformers", "numpy", "mujoco", "robosuite"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "device_name": device_label(gpu, board, platform.node()),
        "hostname": platform.node(), "board": board, "gpu_name": gpu,
        "compute_capability": list(torch.cuda.get_device_capability()),
        "bf16_supported": torch.cuda.is_bf16_supported(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "python": sys.version, "python_executable": sys.executable,
        "torch": str(torch.__version__), "cuda": torch.version.cuda,
        "packages": versions, "platform": platform.platform(),
        "nvpmodel": command_output(["nvpmodel", "-q"]),
        "git_commit": command_output(["git", "rev-parse", "HEAD"]),
        "git_status": command_output(["git", "status", "--short"]),
    }


def local_path(value, env_name, candidates, directory=False):
    explicit = value or os.environ.get(env_name)
    choices = [explicit] if explicit else candidates
    for value in choices:
        path = expand_path(str(value))
        valid = path.is_dir() if directory else path.is_file()
        if valid:
            return str(path.resolve())
    raise FileNotFoundError(f"Set {env_name} or its CLI path option; no valid path among: {choices}")


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


