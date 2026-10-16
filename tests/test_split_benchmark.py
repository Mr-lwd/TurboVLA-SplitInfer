from contextlib import redirect_stdout
from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.libero.benchmark_local import DEFAULT_CONFIG, load_settings, main, summarize
from scripts.libero.summarize_split import export_result


def recorded_result():
    # Legacy result: chunk size exists only in the saved server metadata.
    result = {"policy_backend": "remote", "remote_server": {"gpu_name": "NVIDIA Thor", "chunk_size": 12},
              "num_open_loop_steps": 12, "total_episodes": 2, "total_successes": 2,
              "overall_success_rate": 1, "timing_scope": "rollout", "task_suite_name": "libero_spatial",
              "tasks": [{"task_id": 0, "episode_results": []}]}
    for episode in range(2):
        calls = [{"step": step, "duration_s": duration, "remote": {
            "request_id": f"{episode}-{step}", "server_inference_s": duration / 2,
            "request_bytes": 100, "uncompressed_tensor_bytes": 1000}}
            for step, duration in ((0, 1.0), (12, 0.1))]
        result["tasks"][0]["episode_results"].append({"episode": episode, "executed_steps": 13,
            "rollout_wall_time_s": 2.0, "inference_timings": calls})
    return result


class SplitBenchmarkTests(unittest.TestCase):
    def test_remote_filtering_units_and_missing_data(self):
        summary, rows = summarize(recorded_result(), 1)
        self.assertEqual(summary["chunk_size"], 12)
        self.assertAlmostEqual(summary["filtered_calls"]["mean_ms"], 100)
        stage = summary["remote_stage_timings"]["server_inference_s"]
        self.assertAlmostEqual(stage["filtered_calls"]["mean_ms"], 50)
        self.assertAlmostEqual(stage["all_calls"]["total"], 1.1)
        self.assertEqual(stage["all_calls"]["total_unit"], "s")
        payload = summary["remote_payload"]["request_bytes"]["all_calls"]
        self.assertEqual(payload["mean_bytes"], 100)
        self.assertEqual(payload["total"], 400)
        missing = summary["remote_stage_timings"]["server_queue_s"]["all_calls"]
        self.assertEqual(missing["missing_count"], 4)
        self.assertIsNone(missing["mean_ms"])
        self.assertIsNone(summary["remote_memory"]["server_cuda_peak_allocated_bytes"]["max_bytes"])
        self.assertEqual([r["request_id"] for r in rows], ["0-0", "0-12", "1-0", "1-12"])
        self.assertEqual(summarize(recorded_result(), 2)[0]["filtered_calls"]["count"], 0)
        bad = recorded_result()
        bad["tasks"][0]["episode_results"][0]["inference_timings"][0]["remote"]["server_inference_s"] = float("nan")
        with self.assertRaises(ValueError):
            summarize(bad, 1)

    def test_backfill_preserves_source_and_has_no_invented_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.json"
            path.write_text(json.dumps(recorded_result()))
            original = path.read_bytes()
            prefix = export_result(path, client_device="orin")
            self.assertEqual(path.read_bytes(), original)
            metadata = json.loads(prefix.with_name(prefix.name + "_metadata.json").read_text())
            self.assertIsNone(metadata["client_runtime"])
            self.assertIsNone(metadata["server_runtime"])
            self.assertEqual(metadata["status"], "backfilled")
            with prefix.with_suffix(".csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["server_cuda_peak_allocated_bytes"], "")

    def test_split_runner_needs_no_local_weights_and_exports_stages(self):
        import yaml
        from vla_adapter import rollout

        saved_cwd = Path.cwd()
        self.addCleanup(os.chdir, saved_cwd)
        server = {"gpu_name": "NVIDIA Thor", "hostname": "test-thor", "stats_key": "libero_all4_no_noops", "chunk_size": 12}
        def evaluate(cfg):
            self.assertEqual(cfg.ckpt_path, "")
            self.assertEqual(cfg.dinov3_path, "")
            self.assertEqual(cfg.bert_path, "")
            self.assertEqual(cfg.remote_policy_url, "http://cli:8765")
            result = recorded_result()
            result["remote_server"] = server
            Path(cfg.result_json_path).write_text(json.dumps(result))

        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"THOR_URL": "http://env:8765", "SPLIT_OUTPUT": temp}):
            root = Path(temp)
            for name in ("bddl_files", "init_files", "assets"):
                (root / "libero/libero" / name).mkdir(parents=True)
            settings = load_settings(DEFAULT_CONFIG.with_name("split_benchmark.yaml"), rollout.GenerateConfig, split=True)
            settings["paths"]["libero_root"] = temp
            config = root / "split.yaml"
            config.write_text(yaml.safe_dump(settings))
            argv = ["benchmark_split.py", "--config", str(config), "--remote_policy_url", "http://cli:8765"]
            with patch("sys.argv", argv), redirect_stdout(io.StringIO()), \
                 patch("scripts.libero.benchmark_local.hardware_info", return_value={"device_name": "orin", "gpu_name": "Orin"}), \
                 patch("turbovla.split.client.RemoteTurboVLAPolicy") as remote, \
                 patch("torch.cuda.reset_peak_memory_stats"), \
                 patch("torch.cuda.max_memory_allocated", return_value=0), \
                 patch("torch.cuda.max_memory_reserved", return_value=0), \
                 patch.object(rollout, "eval_libero", side_effect=evaluate):
                remote.return_value.server_info = deepcopy(server)
                remote.return_value.compression = "zlib"
                main(split=True)
            report = next(root.glob("orin_to_thor_split_*/*_summary.json"))
            self.assertEqual(json.loads(report.read_text())["filtered_calls"]["count"], 2)
            metadata = json.loads(next(root.glob("orin_to_thor_split_*/*_metadata.json")).read_text())
            self.assertEqual(metadata["status"], "completed")
            self.assertEqual(metadata["remote_server"], server)


if __name__ == "__main__":
    unittest.main()
