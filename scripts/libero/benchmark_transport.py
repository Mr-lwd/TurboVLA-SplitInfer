"""Compare split transport modes on identical saved observations and verify action parity."""

import argparse
from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np

from scripts.libero.benchmark_common import REMOTE_STAGES, device_label, distribution, hardware_info, write_json
from turbovla.split.client import RemoteTurboVLAPolicy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote_policy_url", required=True)
    parser.add_argument("--baseline_url", help="Optional older server for an additional zlib/close comparison")
    parser.add_argument("--observations", type=Path, required=True,
                        help="NPZ: primary/wrist uint8 [N,256,256,3], state float32 [N,8], instruction strings [N]")
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--output_root", type=Path, default=Path("outputs/evaluation/transport"))
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmup < 0:
        parser.error("Require repetitions >= 1 and warmup >= 0")
    with np.load(args.observations, allow_pickle=False) as archive:
        inputs = {key: archive[key] for key in ("primary", "wrist", "state", "instruction")}
    count = len(inputs["primary"])
    if count < 1 or inputs["state"].shape != (count, 8) or inputs["instruction"].shape != (count,):
        raise ValueError("Invalid observation count/state/instruction shapes")
    for key in ("primary", "wrist"):
        if inputs[key].shape != (count, 256, 256, 3) or inputs[key].dtype != np.uint8:
            raise ValueError(f"Invalid {key} images")
    import torch

    client_info = hardware_info(torch)
    rng = random.Random(args.seed)
    with ExitStack() as stack:
        modes = {"zlib_close": ("zlib", False, args.remote_policy_url),
                 "zlib_keepalive": ("zlib", True, args.remote_policy_url),
                 "zlib_shuffle_keepalive": ("zlib_shuffle", True, args.remote_policy_url),
                 "lz4_keepalive": ("lz4", True, args.remote_policy_url),
                 "lz4_shuffle_keepalive": ("lz4_shuffle", True, args.remote_policy_url),
                 "zstd_keepalive": ("zstd", True, args.remote_policy_url),
                 "zstd_shuffle_keepalive": ("zstd_shuffle", True, args.remote_policy_url)}
        if args.baseline_url:
            modes["baseline_server_zlib_close"] = ("zlib", False, args.baseline_url)
        clients, skipped = {}, {}
        for name, (codec, keepalive, url) in modes.items():
            try:
                clients[name] = stack.enter_context(RemoteTurboVLAPolicy(
                    url, precision=args.precision, compression=codec, keepalive=keepalive))
            except ValueError as exc:
                if "unavailable on both devices" not in str(exc):
                    raise
                skipped[name] = str(exc)
        if not clients:
            raise RuntimeError("No usable transport modes")
        identities = {(c.server_info["checkpoint_sha256"], c.server_info["stats_key"])
                      for c in clients.values()}
        if len(identities) != 1:
            raise ValueError("Benchmark servers must use the same checkpoint and stats key")
        reference, samples = {}, {name: [] for name in clients}
        def call(name, index, measured):
            client = clients[name]
            start = time.perf_counter()
            actions = client.predict_env_action_chunk(
                inputs["primary"][index], inputs["wrist"][index], str(inputs["instruction"][index]),
                inputs["state"][index], execute_steps=12)
            duration = time.perf_counter() - start
            if index not in reference:
                reference[index] = actions.copy()
            # Same GPU, tensors and policy: require exact action equality.
            if not np.array_equal(reference[index], actions):
                raise AssertionError(f"Action parity failed for {name}, observation {index}")
            if measured:
                samples[name].append({"observation": index, "duration_s": duration,
                                      "exact_action_equal": True, **client.last_timing})
        for _ in range(args.warmup):
            for index in range(count):
                for name in clients:
                    call(name, index, False)
        for repetition in range(args.repetitions):
            index = repetition % count
            order = list(clients)
            rng.shuffle(order)  # Interleave to reduce ordering/thermal/network bias.
            for name in order:
                call(name, index, True)
            print(f"Measured round {repetition + 1}/{args.repetitions}", flush=True)
        reports = {}
        for name, rows in samples.items():
            reports[name] = {
                "complete_call": distribution([r["duration_s"] for r in rows]),
                "stages": {key: distribution([r[key] for r in rows if key in r]) for key in REMOTE_STAGES},
                "request_size": distribution([r["request_bytes"] for r in rows], "bytes", 1),
                "connection_reused_count": sum(r["connection_reused"] for r in rows),
                "samples": rows,
            }
        tag = client_info["device_name"] + "_to_" + device_label(
            next(iter(clients.values())).server_info.get("gpu_name", ""), "", "server")
        stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
        output = args.output_root / f"{tag}_transport_{stamp}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, {
            "scope": "fixed-observation policy-call benchmark; excludes simulator, rendering and video; not a success-rate evaluation",
            "client": client_info, "servers": {name: c.server_info for name, c in clients.items()},
            "observations": str(args.observations.resolve()),
            "observations_sha256": hashlib.sha256(args.observations.read_bytes()).hexdigest(),
            "warmup_rounds_per_observation_per_mode": args.warmup,
            "measured_calls_per_mode": args.repetitions, "seed": args.seed,
            "exact_action_parity": True, "skipped": skipped, "modes": reports,
        })
        for name, report in reports.items():
            print(name, report["complete_call"], flush=True)
        print(f"Saved: {output}")


if __name__ == "__main__":
    main()
