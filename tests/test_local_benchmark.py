from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.libero.benchmark_local import (
    DEFAULT_CONFIG, device_label, distribution, expand_path, load_settings,
    local_path, main, summarize,
)


class LocalBenchmarkTests(unittest.TestCase):
    def test_hardware_identification_and_safe_fallback(self):
        self.assertEqual(device_label("Orin", "", "thor-host"), "orin")
        self.assertEqual(device_label("NVIDIA Thor", "", "ubuntu"), "thor")
        self.assertEqual(device_label("", "NVIDIA Jetson Orin NX", "node1"), "orin")
        self.assertEqual(device_label("GPU / Test", "", "node1"), "gpu_test")

    def test_percentile_and_empty_samples(self):
        self.assertIsNone(distribution([])["mean_ms"])
        self.assertAlmostEqual(distribution([0.1, 0.3])["p95_ms"], 290)

    def test_config_validation_and_path_precedence(self):
        import yaml
        from vla_adapter.rollout import GenerateConfig

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = load_settings(DEFAULT_CONFIG, GenerateConfig)
            for name in ("cli", "env", "yaml"):
                (root / name).touch()
            with patch.dict(os.environ, {"CKPT_PATH": str(root / "env"), "TEST_MODELS": temp}):
                self.assertEqual(local_path(str(root / "cli"), "CKPT_PATH", [root / "yaml"]), str(root / "cli"))
                self.assertEqual(local_path("", "CKPT_PATH", [root / "yaml"]), str(root / "env"))
                self.assertEqual(expand_path("${TEST_MODELS}/yaml"), root / "yaml")
            self.assertEqual(expand_path("${libero_root}/data", temp), root / "data")
            path = root / "test.yaml"
            config["evaluation"]["num_trials_per_task"] = "3"
            path.write_text(yaml.safe_dump(config))
            with self.assertRaisesRegex(ValueError, "num_trials_per_task must be int"):
                load_settings(path, GenerateConfig)
            config["evaluation"]["num_trials_per_task"] = 3
            config["evaluation"]["unknown_option"] = True
            path.write_text(yaml.safe_dump(config))
            with self.assertRaisesRegex(ValueError, "unknown_option"):
                load_settings(path, GenerateConfig)

    def test_filters_each_episode_and_counts_partial_chunk(self):
        episodes = []
        for index in range(2):
            episodes.append({"episode": index, "executed_steps": 13,
                             "rollout_wall_time_s": 4,
                             "inference_timings": [{"step": 0, "duration_s": 1},
                                                   {"step": 12, "duration_s": 0.12}]})
        result = {"policy_backend": "local", "chunk_size": 12, "num_open_loop_steps": 12,
                  "total_episodes": 2, "total_successes": 1, "overall_success_rate": 0.5,
                  "timing_scope": "rollout", "tasks": [{"task_id": 0, "episode_results": episodes}]}
        summary, rows = summarize(result, 1)
        self.assertEqual(summary["all_calls"]["count"], 4)
        self.assertEqual(summary["filtered_calls"]["count"], 2)
        self.assertAlmostEqual(summary["filtered_amortized_ms_per_predicted_action"], 10)
        self.assertEqual(summary["executed_steps"], 26)
        self.assertAlmostEqual(summary["non_inference_rollout_s"], 5.76)
        self.assertEqual([r["included_in_filtered"] for r in rows], [False, True, False, True])
        self.assertIsNone(summarize(result, 2)[0]["filtered_amortized_ms_per_predicted_action"])
        result["policy_backend"] = "remote"
        with self.assertRaises(ValueError):
            summarize(result, 1)

    def test_runner_exports_device_named_files_and_records_failure(self):
        import yaml
        from vla_adapter import rollout

        def evaluate(cfg):
            self.assertEqual(cfg.seed, 19)  # CLI overrides YAML.
            self.assertFalse(cfg.save_video)  # YAML overrides evaluator defaults.
            self.assertEqual(cfg.num_trials_per_task, 3)
            paths = yaml.safe_load((Path(os.environ["LIBERO_CONFIG_PATH"]) / "config.yaml").read_text())
            self.assertEqual(paths["datasets"], str(root / "custom_data"))
            Path(cfg.result_json_path).write_text(json.dumps({
                "policy_backend": "local", "chunk_size": 12, "num_open_loop_steps": 12,
                "total_episodes": 0, "total_successes": 0, "overall_success_rate": 0,
                "timing_scope": "rollout", "tasks": []}))

        original_cwd = Path.cwd()
        self.addCleanup(os.chdir, original_cwd)
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ):
            root = Path(temp)
            checkpoint = root / "checkpoint.pth"
            checkpoint.touch()
            for name in ("bddl_files", "init_files", "assets"):
                (root / "libero/libero" / name).mkdir(parents=True)
            settings = load_settings(DEFAULT_CONFIG, rollout.GenerateConfig)
            settings["benchmark"]["output_root"] = temp
            settings["evaluation"].update(seed=11, save_video=False, num_trials_per_task=3)
            settings["libero_paths"]["datasets"] = "${libero_root}/custom_data"
            config = root / "custom.yaml"
            config.write_text(yaml.safe_dump(settings))
            argv = ["benchmark_local.py", "--config", str(config), "--seed", "19", "--ckpt_path", str(checkpoint),
                    "--libero_root", temp, "--dinov3_path", temp, "--bert_path", temp,
                    "--stats_path", str(checkpoint)]
            with patch("sys.argv", argv), redirect_stdout(io.StringIO()), \
                 patch("scripts.libero.benchmark_local.hardware_info", return_value={
                     "device_name": "thor", "gpu_name": "NVIDIA Thor", "bf16_supported": True}), \
                 patch("torch.cuda.reset_peak_memory_stats"), \
                 patch("torch.cuda.max_memory_allocated", return_value=100), \
                 patch("torch.cuda.max_memory_reserved", return_value=200), \
                 patch.object(rollout, "eval_libero", side_effect=evaluate) as evaluator:
                main()
                summary = next(root.glob("thor_*/*_summary.json"))
                self.assertEqual(json.loads(summary.read_text())["all_calls"]["count"], 0)
                self.assertEqual(len(list(root.glob("thor_*/*.csv"))), 1)
                evaluator.side_effect = RuntimeError("evaluation failed")
                with self.assertRaisesRegex(RuntimeError, "evaluation failed"):
                    main()
                states = [json.loads(p.read_text())["status"] for p in root.glob("thor_*/*_metadata.json")]
                self.assertCountEqual(states, ["completed", "failed"])


if __name__ == "__main__":
    unittest.main()
