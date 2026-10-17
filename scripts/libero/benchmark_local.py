"""Run device-labelled local LIBERO inference benchmarks."""

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.libero.benchmark_common import (
    DEFAULT_CONFIG, LIBERO_KEYS, PATH_ENV, REPO_ROOT, control_step_rows, expand_path,
    hardware_info, load_settings, local_path, summarize, write_json, write_reports,
)


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
    if cfg.remote_policy_url:
        parser.error("Use run_async_benchmark.sh for remote inference (sync/replace/blend)")
    if cfg.dry_run_model_load:
        parser.error("Use --print_command for preflight")
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
    device_tag = metadata["device_name"]
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
    run_name = f"{device_tag}_{cfg.task_suite_name}_{cfg.precision}_{stamp}"
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
        write_reports(prefix, summary, rows, control_step_rows(result))
        metadata["status"] = "completed"
        print(json.dumps({k: summary[k] for k in ("all_calls", "filtered_calls", "control_intervals", "overall_success_rate")}, indent=2))
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
