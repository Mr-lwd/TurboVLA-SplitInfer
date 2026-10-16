"""Exercise the unified entry point and standalone config without hardware or weights."""

from contextlib import redirect_stdout
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from scripts.libero import benchmark_async
from scripts.libero.benchmark_common import REPO_ROOT, load_settings
from vla_adapter import rollout


class FakeEnvironment:
    def __init__(self):
        self.closed = False
        self.count = 0

    def reset(self):
        self.count = 0

    def observation(self):
        image = np.zeros((4, 4, 3), np.uint8)
        return {"agentview_image": image, "robot0_eye_in_hand_image": image.copy(),
                "robot0_eef_pos": np.zeros(3), "robot0_eef_quat": np.array([0., 0., 0., 1.]),
                "robot0_gripper_qpos": np.zeros(2)}

    def set_init_state(self, state):
        return self.observation()

    def step(self, action):
        self.count += 1
        return self.observation(), 0, self.count == 6, {}

    def close(self):
        self.closed = True


class FakeRemotePolicy:
    server_info = {"stats_key": "libero_all4_no_noops", "gpu_name": "NVIDIA Thor"}
    compression = "zstd_shuffle"
    last_timing = {"server_inference_s": .01}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def predict_env_action_chunk(self, *args, execute_steps):
        actions = np.zeros((execute_steps, 7), np.float32)
        actions[:, 6] = -1
        return actions


class AsyncBenchmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config_path = self.root / "benchmark.yaml"
        self.output = self.root / "runs"
        for name in ("bddl_files", "init_files", "assets"):
            (self.root / "libero/libero" / name).mkdir(parents=True)
        self.settings = load_settings(REPO_ROOT / "experiments/libero/configs/async_benchmark.yaml",
                                      rollout.GenerateConfig, remote=True)
        self.settings["paths"]["libero_root"] = str(self.root)
        self.settings["benchmark"]["output_root"] = str(self.output)
        self.settings["evaluation"].update(task_ids="0", num_steps_wait=0, save_video=False)
        self.settings["experiment"].update(control_hz=1000., replan_every_steps=1, blend_steps=2)
        self.write_config()
        self.addCleanup(os.chdir, Path.cwd())
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("LIBERO_ROOT", None)
        os.environ["THOR_URL"] = "http://env:8765"
        self.environments = []
        self.configs = []

    def write_config(self):
        self.config_path.write_text(yaml.safe_dump(self.settings))

    def invoke(self, *options, failure=None):
        suite = SimpleNamespace(n_tasks=1, get_task=lambda _: SimpleNamespace(language="test task"),
                                get_task_init_states=lambda _: [np.zeros(1)])
        package = ModuleType("libero")
        module = ModuleType("libero.libero")
        module.benchmark = SimpleNamespace(get_benchmark_dict=lambda: {"libero_spatial": lambda: suite})
        package.libero = module
        def make_env(task, cfg):
            if failure:
                raise failure
            self.configs.append(cfg)
            env = FakeEnvironment()
            self.environments.append(env)
            return env, task.language
        argv = ["benchmark_async.py", "--config", str(self.config_path), *options]
        with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()), \
             patch.dict(sys.modules, {"libero": package, "libero.libero": module}), \
             patch.object(benchmark_async, "hardware_info", return_value={"device_name": "orin", "gpu_name": "Orin"}), \
             patch.object(rollout, "_ensure_libero_import_path"), \
             patch.object(rollout, "_setup_logging"), \
             patch.object(rollout, "_make_libero_env", side_effect=make_env), \
             patch("turbovla.evaluation.suite_policy.set_seed_everywhere"), \
             patch("turbovla.split.client.RemoteTurboVLAPolicy", return_value=FakeRemotePolicy()) as remote:
            benchmark_async.main()
        return remote

    def test_standalone_config_runs_all_modes_without_local_weights(self):
        remote = self.invoke("--remote_policy_url", "http://cli:8765", "--exclude_first_calls", "0",
                             "--libero_datasets", str(self.root / "custom_data"))
        self.assertEqual(remote.call_args.args, ("http://cli:8765",))
        self.assertEqual(len(self.environments), 3)
        self.assertTrue(all(e.closed for e in self.environments))
        self.assertTrue(all(not c.ckpt_path and not c.dinov3_path and not c.bert_path for c in self.configs))
        comparison = json.loads(next(self.output.glob("*/*_comparison.json")).read_text())
        self.assertEqual(set(comparison), {"sync", "replace", "blend"})
        for summary in comparison.values():
            self.assertEqual(summary["successes"], 1)
            self.assertEqual(summary["executed_steps"], 6)
            self.assertEqual(summary["all_calls"]["count"], summary["filtered_calls"]["count"])
            self.assertGreater(summary["remote_stage_timings"]["server_inference_s"]["all_calls"]["count"], 0)
        metadata = json.loads(next(self.output.glob("*/*_metadata.json")).read_text())
        self.assertEqual(metadata["status"], "completed")
        self.assertNotIn("base_config", metadata)
        self.assertEqual(metadata["exclude_first_calls_per_episode"], 0)
        self.assertEqual(metadata["resolved_libero_paths"]["datasets"], str(self.root / "custom_data"))
        self.assertEqual(len(list(self.output.glob("*/*_calls.csv"))), 3)
        self.assertEqual(len(list(self.output.glob("*/*_steps.csv"))), 3)

    def test_sync_only_uses_same_entry_with_cli_output_override(self):
        output = self.root / "cli_output"
        self.invoke("--modes", "sync", "--output_root", str(output))
        self.assertFalse(self.output.exists())
        comparison = json.loads(next(output.glob("*/*_comparison.json")).read_text())
        self.assertEqual(set(comparison), {"sync"})
        self.assertEqual(comparison["sync"]["all_calls"]["count"], 1)
        self.assertEqual(comparison["sync"]["filtered_calls"]["count"], 0)

    def test_preflight_resolves_config_and_env_without_creating_outputs(self):
        remote = self.invoke("--preflight")
        self.assertEqual(remote.call_args.args, ("http://env:8765",))
        self.assertFalse(self.output.exists())
        self.assertEqual(self.environments, [])

    def test_failure_is_recorded_without_completed_comparison(self):
        with self.assertRaisesRegex(RuntimeError, "environment failed"):
            self.invoke(failure=RuntimeError("environment failed"))
        metadata = json.loads(next(self.output.glob("*/*_metadata.json")).read_text())
        self.assertEqual(metadata["status"], "failed")
        self.assertFalse(list(self.output.glob("*/*_comparison.json")))

    def test_legacy_config_has_actionable_migration_error(self):
        self.config_path.write_text("base_config: obsolete.yaml\nevaluation: {}\nexperiment: {}\n")
        with self.assertRaisesRegex(ValueError, "standalone async_benchmark.yaml"):
            self.invoke("--preflight")

    def test_invalid_config_fails_before_contacting_server(self):
        for section, key, value in (("benchmark", "exclude_first_calls", -1),
                                    ("evaluation", "num_trials_per_task", "3"),
                                    ("evaluation", "ckpt_path", "/unused/weights.pth")):
            with self.subTest(section=section, key=key):
                original = self.settings[section].copy()
                self.settings[section][key] = value
                self.write_config()
                with patch("turbovla.split.client.RemoteTurboVLAPolicy") as remote:
                    with self.assertRaises(ValueError):
                        benchmark_async.load_settings(self.config_path, rollout.GenerateConfig, remote=True)
                    remote.assert_not_called()
                self.settings[section] = original


if __name__ == "__main__":
    unittest.main()
