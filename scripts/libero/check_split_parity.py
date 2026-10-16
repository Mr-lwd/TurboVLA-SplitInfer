"""On Thor, compare direct inference against the HTTP tensor path."""

import argparse
import json
from pathlib import Path

import numpy as np

from turbovla.evaluation.suite_policy import TurboVLAPolicy
from turbovla.split.client import RemoteTurboVLAPolicy
from turbovla.split.server import build_metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote_policy_url", required=True)
    parser.add_argument("--ckpt_path", required=True)
    parser.add_argument("--dinov3_path", required=True)
    parser.add_argument("--bert_path", required=True)
    parser.add_argument("--stats_path", default="experiments/libero/configs/libero_all4_stats.json")
    parser.add_argument("--stats_key", default="libero_all4_no_noops")
    parser.add_argument("--result_json_path", default="outputs/split/parity.json")
    args = parser.parse_args()
    remote = RemoteTurboVLAPolicy(args.remote_policy_url)
    local = TurboVLAPolicy(
        ckpt_path=args.ckpt_path, dinov3_path=args.dinov3_path, bert_path=args.bert_path,
        stats_path=args.stats_path, stats_key=args.stats_key, precision="bf16", device="cuda",
    )
    if build_metadata(local)["checkpoint_sha256"] != remote.server_info["checkpoint_sha256"]:
        raise RuntimeError("direct and remote policies use different checkpoint files")
    rng = np.random.default_rng(7)
    instruction = "pick up the black bowl between the plate and the ramekin and place it on the plate"
    results = []
    for index in range(3):
        primary = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
        wrist = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
        state = local.proprio_mean + rng.normal(0, 0.1, 8).astype(np.float32) * local.proprio_std
        expected = local.predict_env_action_chunk(primary, wrist, instruction, state, execute_steps=12)
        actual = remote.predict_env_action_chunk(primary, wrist, instruction, state, execute_steps=12)
        result = {"case": index, "max_abs_error": float(np.max(np.abs(expected - actual))),
                  "exact_equal": bool(np.array_equal(expected, actual))}
        results.append(result)
        print(result, flush=True)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-6)
    path = Path(args.result_json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"passed": True, "cases": results,
                                "checkpoint_sha256": remote.server_info["checkpoint_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
