"""Run local LIBERO evaluation and save device-labelled latency measurements."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
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
    choices = [Path(explicit).expanduser()] if explicit else candidates
    for path in choices:
        path = path if path.is_absolute() else REPO_ROOT / path
        valid = path.is_dir() if directory else path.is_file()
        if valid:
            return str(path.resolve())
    raise FileNotFoundError(f"Set {env_name} or its CLI path option; no valid path among: {choices}")


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
        epilog="Other options are forwarded to evaluate.py (e.g. --task_ids 0 --save_video false).")
    parser.add_argument("--output_root", "--output-root", default="outputs/evaluation/local")
    parser.add_argument("--exclude_first_calls", "--exclude-first-calls", type=int, default=1)
    parser.add_argument("--print_command", "--print-command", action="store_true", help="Validate paths/device and print configuration without loading the model")
    args, remaining = parser.parse_known_args()
    if args.exclude_first_calls < 0:
        parser.error("exclude_first_calls must be nonnegative")
    os.chdir(REPO_ROOT)
    # Support direct execution before an editable installation.
    sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "third_party/vla_adapter")]
    from vla_adapter.rollout import eval_libero, parse_args
    cfg = parse_args(["--task_suite_name", "libero_spatial", "--num_trials_per_task", "1",
                      "--save_video", "true", "--mujoco_gl", "egl", "--pyopengl_platform", "egl", *remaining])
    if cfg.remote_policy_url or cfg.dry_run_model_load:
        parser.error("Use local rollouts only; for a configuration check use --print_command")
    if cfg.num_trials_per_task < 1 or cfg.chunk_size < 1 or not 1 <= cfg.num_open_loop_steps <= cfg.chunk_size:
        parser.error("Require trials >= 1 and 1 <= num_open_loop_steps <= chunk_size")
    if cfg.result_json_path or cfg.log_path or cfg.video_out_path != "outputs/evaluation":
        parser.error("Output paths are automatically named; use --output_root")
    cfg.ckpt_path = local_path(cfg.ckpt_path, "CKPT_PATH", [REPO_ROOT / "pretrained/TurboVLA/checkpoints/libero/turbovla_libero.pth"])
    cfg.libero_root = local_path(cfg.libero_root, "LIBERO_ROOT", [REPO_ROOT.parent / "LIBERO"], directory=True)
    model_roots = [REPO_ROOT.parent / "models", Path.home() / "models", REPO_ROOT / "models"]
    cfg.dinov3_path = local_path(cfg.dinov3_path, "DINOV3_PATH", [p / "DINOv3" for p in model_roots], directory=True)
    cfg.bert_path = local_path(cfg.bert_path, "BERT_PATH", [p / "bert-base-uncased" for p in model_roots], directory=True)
    cfg.stats_path = local_path(cfg.stats_path, "STATS_PATH", [])
    os.environ["MUJOCO_GL"] = cfg.mujoco_gl
    os.environ["PYOPENGL_PLATFORM"] = cfg.pyopengl_platform
    import torch
    metadata = hardware_info(torch)
    if cfg.precision == "bf16" and not metadata["bf16_supported"]:
        raise RuntimeError("This CUDA device does not support bf16; select --precision fp32")
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
    run_name = f"{metadata['device_name']}_{cfg.task_suite_name}_{cfg.precision}_{stamp}"
    run_dir = Path(args.output_root).expanduser().resolve() / run_name
    prefix = run_dir / run_name
    cfg.result_json_path = str(prefix.with_suffix(".json"))
    cfg.log_path = str(prefix.with_suffix(".log"))
    cfg.video_out_path = str(run_dir / f"{metadata['device_name']}_videos")
    command = [sys.executable, "experiments/libero/evaluate.py"]
    for name, value in asdict(cfg).items():
        command.extend([f"--{name}", str(value).lower() if isinstance(value, bool) else str(value)])
    print(f"Device: {metadata['device_name']} ({metadata['gpu_name']})\nOutput: {run_dir}", flush=True)
    if args.print_command:
        print(shlex.join(command))
        return
    run_dir.mkdir(parents=True, exist_ok=False)
    metadata.update({"config": asdict(cfg), "command": command, "started_at": stamp,
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
