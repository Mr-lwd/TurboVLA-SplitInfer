"""Run local LIBERO evaluation and save device-labelled latency measurements."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, fields
from datetime import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "experiments/libero/configs/local_benchmark.yaml"
PATH_ENV = {"ckpt_path": "CKPT_PATH", "libero_root": "LIBERO_ROOT",
            "dinov3_path": "DINOV3_PATH", "bert_path": "BERT_PATH", "stats_path": "STATS_PATH"}
LIBERO_KEYS = {"benchmark_root", "bddl_files", "init_states", "assets", "datasets"}


def expand_path(value, libero_root=None):
    value = value.replace("${REPO_ROOT}", str(REPO_ROOT))
    if libero_root is not None:
        value = value.replace("${libero_root}", str(libero_root))
    value = os.path.expandvars(value)
    if "$" in value:
        raise ValueError(f"Unresolved variable in path: {value}")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


def load_settings(path, config_type):
    import yaml

    with path.open(encoding="utf-8") as stream:
        settings = yaml.safe_load(stream)
    sections = {"paths", "libero_paths", "benchmark", "evaluation"}
    if not isinstance(settings, dict) or set(settings) != sections:
        raise ValueError(f"Config requires exactly these sections: {sorted(sections)}")
    for section in sections:
        if not isinstance(settings[section], dict):
            raise ValueError(f"{section} must be a mapping")
    for section, keys in (("paths", set(PATH_ENV)), ("libero_paths", LIBERO_KEYS),
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


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "mean_ms": None, "median_ms": None,
                "p95_ms": None, "min_ms": None, "max_ms": None}
    position = (len(values) - 1) * 0.95
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return {"count": len(values), "mean_ms": statistics.mean(values) * 1000,
            "median_ms": statistics.median(values) * 1000,
            "p95_ms": (values[lo] + (values[hi] - values[lo]) * (position - lo)) * 1000,
            "min_ms": values[0] * 1000, "max_ms": values[-1] * 1000}


def summarize(result, exclude_first_calls):
    if result.get("policy_backend") != "local":
        raise ValueError("This benchmark requires local inference")
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
    all_calls = [row["duration_s"] for row in rows]
    filtered = [row["duration_s"] for row in rows if row["included_in_filtered"]]
    first_calls = [row["duration_s"] for row in rows if row["call_index"] == 0]
    wall = sum(ep["rollout_wall_time_s"] for ep in episodes)
    inference = sum(all_calls)
    steps = sum(ep["executed_steps"] for ep in episodes)
    chunk = result["chunk_size"]
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
        "inference_total_s": inference, "non_inference_rollout_s": wall - inference,
        "non_inference_scope": "simulation, rendering, image preparation and Python overhead; not environment stepping alone",
        "inference_fraction_of_rollout": inference / wall if wall else None,
        "executed_steps_per_rollout_second": steps / wall if wall else None,
        "rollout_scope": result["timing_scope"],
    }
    return summary, rows


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


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
        epilog="Other options are forwarded to evaluate.py (e.g. --task_ids 0 --save_video false).")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Benchmark YAML configuration")
    parser.add_argument("--output_root", "--output-root")
    parser.add_argument("--exclude_first_calls", "--exclude-first-calls", type=int)
    for key in sorted(LIBERO_KEYS):
        parser.add_argument(f"--libero_{key}", f"--libero-{key.replace('_', '-')}")
    parser.add_argument("--print_command", "--print-command", action="store_true", help="Validate paths/device and print configuration without loading the model")
    args, remaining = parser.parse_known_args()
    os.chdir(REPO_ROOT)
    # Support direct execution before an editable installation.
    sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "third_party/vla_adapter")]
    from vla_adapter.rollout import GenerateConfig, eval_libero, parse_args
    config_path = expand_path(args.config)
    settings = load_settings(config_path, GenerateConfig)
    if args.output_root is None:
        args.output_root = settings["benchmark"]["output_root"]
    if args.exclude_first_calls is None:
        args.exclude_first_calls = settings["benchmark"]["exclude_first_calls"]
    if args.exclude_first_calls < 0:
        parser.error("exclude_first_calls must be nonnegative")
    defaults = []
    for key, value in settings["evaluation"].items():
        defaults.extend([f"--{key}", str(value).lower() if isinstance(value, bool) else str(value)])
    # Empty evaluator defaults allow path precedence: CLI > environment > YAML.
    for key in PATH_ENV:
        defaults.extend([f"--{key}", ""])
    cfg = parse_args([*defaults, *remaining])
    if cfg.remote_policy_url or cfg.dry_run_model_load:
        parser.error("Use local rollouts only; for a configuration check use --print_command")
    if cfg.num_trials_per_task < 1 or cfg.chunk_size < 1 or not 1 <= cfg.num_open_loop_steps <= cfg.chunk_size:
        parser.error("Require trials >= 1 and 1 <= num_open_loop_steps <= chunk_size")
    if cfg.result_json_path or cfg.log_path or cfg.video_out_path != "outputs/evaluation":
        parser.error("Output paths are automatically named; use --output_root")
    for key, env_name in PATH_ENV.items():
        candidates = settings["paths"][key]
        candidates = candidates if isinstance(candidates, list) else [candidates]
        setattr(cfg, key, local_path(getattr(cfg, key), env_name, candidates,
                                    directory=key not in {"ckpt_path", "stats_path"}))
    libero_paths = {}
    for key, value in settings["libero_paths"].items():
        path = expand_path(getattr(args, f"libero_{key}") or value, cfg.libero_root)
        # Demonstration datasets are not consumed by online rollouts.
        if key != "datasets" and not path.is_dir():
            raise FileNotFoundError(f"libero_paths.{key} directory not found: {path}")
        libero_paths[key] = str(path)
    os.environ["MUJOCO_GL"] = cfg.mujoco_gl
    os.environ["PYOPENGL_PLATFORM"] = cfg.pyopengl_platform
    import torch
    metadata = hardware_info(torch)
    if cfg.precision == "bf16" and not metadata["bf16_supported"]:
        raise RuntimeError("This CUDA device does not support bf16; select --precision fp32")
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
    run_name = f"{metadata['device_name']}_{cfg.task_suite_name}_{cfg.precision}_{stamp}"
    run_dir = expand_path(args.output_root) / run_name
    prefix = run_dir / run_name
    cfg.result_json_path = str(prefix.with_suffix(".json"))
    cfg.log_path = str(prefix.with_suffix(".log"))
    cfg.video_out_path = str(run_dir / f"{metadata['device_name']}_videos")
    command = [sys.executable, "experiments/libero/evaluate.py"]
    for name, value in asdict(cfg).items():
        command.extend([f"--{name}", str(value).lower() if isinstance(value, bool) else str(value)])
    print(f"Device: {metadata['device_name']} ({metadata['gpu_name']})\nOutput: {run_dir}", flush=True)
    print(f"Config: {config_path}\nLIBERO paths: {json.dumps(libero_paths, ensure_ascii=False)}", flush=True)
    if args.print_command:
        print("The benchmark runner will create libero_config/config.yaml and set LIBERO_CONFIG_PATH before this evaluator command:")
        print(shlex.join(command))
        return
    run_dir.mkdir(parents=True, exist_ok=False)
    import yaml

    libero_config_dir = run_dir / "libero_config"
    libero_config_dir.mkdir()
    (libero_config_dir / "config.yaml").write_text(yaml.safe_dump(libero_paths), encoding="utf-8")
    os.environ["LIBERO_CONFIG_PATH"] = str(libero_config_dir)
    metadata.update({"config": asdict(cfg), "command": command, "started_at": stamp,
                     "config_file": str(config_path), "config_file_contents": settings,
                     "libero_paths": libero_paths, "libero_config_path": str(libero_config_dir),
                     "exclude_first_calls_per_episode": args.exclude_first_calls, "status": "running"})
    metadata_path = prefix.with_name(run_name + "_metadata.json")
    write_json(metadata_path, metadata)
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    try:
        eval_libero(cfg)
        result = json.loads(Path(cfg.result_json_path).read_text())
        summary, rows = summarize(result, args.exclude_first_calls)
        summary.update({"device_name": metadata["device_name"], "source_result": cfg.result_json_path,
                        "metadata_path": str(metadata_path)})
        write_json(prefix.with_name(run_name + "_summary.json"), summary)
        with prefix.with_suffix(".csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["task_id", "episode", "call_index", "step", "duration_s", "duration_ms", "included_in_filtered"])
            writer.writeheader()
            writer.writerows(rows)
        metadata["status"] = "completed"
        print(json.dumps({k: summary[k] for k in ("all_calls", "filtered_calls", "overall_success_rate")}, indent=2))
    except BaseException as exc:
        metadata.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        metadata["evaluation_process_wall_time_s"] = time.perf_counter() - start
        metadata["evaluation_process_scope"] = "model load, environment creation/reset/settling, rollout, video encoding and result export; excludes initial preflight"
        metadata["cuda_peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        metadata["cuda_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
        metadata["memory_scope"] = "PyTorch allocator peak since preflight; not total shared RAM or simulator GPU memory"
        write_json(metadata_path, metadata)
    print(f"Saved benchmark: {run_dir}")


if __name__ == "__main__":
    main()
