from types import SimpleNamespace
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import numpy as np

from scripts.libero.benchmark_async import summarize_episodes
from turbovla.evaluation.async_rollout import ActionTimeline, AsyncEpisode, overlap_seconds, run_episode, save_realtime_video, video_phase


def chunk(values, gripper=-1):
    result = np.repeat(np.asarray(values, dtype=np.float32)[:, None], 7, axis=1)
    result[:, 6] = gripper
    return result


class TimelineTests(unittest.TestCase):
    def test_replace_aligns_to_executed_steps_and_drops_old_tail(self):
        timeline = ActionTimeline()
        timeline.merge(chunk(range(12)), 0, 0, "replace", 3)
        event = timeline.merge(chunk([20, 21, 22, 23]), 4, 6, "replace", 3)
        self.assertEqual(event["discarded_prefix_actions"], 2)
        self.assertEqual(list(timeline.actions), [6, 7])
        action, origin = timeline.pop(6)
        self.assertEqual(action[0], 22)
        self.assertEqual(origin, 4)
        self.assertEqual(timeline.pop(6), (None, None))

    def test_blend_only_overlapping_arm_actions_and_discrete_gripper(self):
        timeline = ActionTimeline()
        timeline.merge(chunk([0] * 6, -1), 0, 0, "replace", 3)
        event = timeline.merge(chunk([3] * 6, 1), 1, 2, "blend", 3)
        self.assertEqual(event["blended_steps"], 3)
        np.testing.assert_allclose([timeline.actions[i][0] for i in range(2, 7)], [1, 2, 3, 3, 3])
        self.assertEqual([timeline.actions[i][6] for i in range(2, 7)], [-1, 1, 1, 1, 1])
        self.assertEqual([timeline.origins[i] for i in range(2, 7)], [0, 0, 1, 1, 1])

    def test_expired_result_does_not_destroy_existing_future(self):
        timeline = ActionTimeline()
        timeline.merge(chunk([5] * 6), 0, 0, "replace", 3)
        event = timeline.merge(chunk([8, 9]), 1, 4, "blend", 3)
        self.assertTrue(event["expired"])
        self.assertEqual(list(timeline.actions), [4, 5])
        self.assertEqual(timeline.actions[4][0], 5)

    def test_nonfinite_or_invalid_chunks_rejected(self):
        for invalid in (np.zeros((2, 6)), np.full((2, 7), np.nan)):
            with self.assertRaises(ValueError):
                ActionTimeline().merge(invalid, 0, 0, "replace", 3)


class FakeEnvironment:
    def __init__(self, started, release):
        self.started, self.release = started, release
        self.count = 0
        self.obs = {"agentview_image": np.zeros((2, 2, 3), np.uint8),
                    "robot0_eye_in_hand_image": np.zeros((2, 2, 3), np.uint8),
                    "state": np.zeros(8, np.float32)}

    def reset(self):
        pass

    def set_init_state(self, state):
        return self.obs

    def step(self, action):
        if self.count == 1 and not self.started.wait(5):
            raise AssertionError("Background request never started")
        self.count += 1
        for value in self.obs.values():
            value.fill(self.count)  # Deliberately reuse all observation buffers.
        if self.count == 5:
            self.release.set()
        return self.obs, 0, self.count == 5, {}


class WorkerTests(unittest.TestCase):
    def run_fake(self, fail=False):
        started, release = threading.Event(), threading.Event()
        env = FakeEnvironment(started, release)
        class Policy:
            calls = 0
            snapshots = []
            last_timing = {"server_inference_s": 0.02}
            def predict_env_action_chunk(self, primary, wrist, instruction, state, execute_steps):
                self.calls += 1
                if self.calls == 2:
                    started.set()
                    if not release.wait(5):
                        raise AssertionError("Control did not continue during inference")
                    self.snapshots.append((primary.copy(), wrist.copy(), state.copy()))
                    if fail:
                        raise RuntimeError("network failed")
                return chunk([0.2] * execute_steps)
        policy = Policy()
        cfg = SimpleNamespace(control_mode="relative", chunk_size=3, num_steps_wait=0,
                              task_suite_name="libero_spatial")
        with patch("turbovla.evaluation.policy.rotate_libero_image", side_effect=lambda value: value), \
             patch("turbovla.evaluation.policy.state_from_libero_obs", side_effect=lambda obs: obs["state"]):
            episode = run_episode(cfg, env, policy, "test", None, "replace",
                                  replan_every_steps=1, blend_steps=2, control_hz=1e6, max_steps=5)
        return episode, policy

    def test_background_snapshots_single_request_hold_and_drain(self):
        episode, policy = self.run_fake()
        self.assertTrue(episode.success)
        self.assertEqual(policy.calls, 2)
        self.assertEqual(len(episode.calls), 2)
        self.assertEqual(episode.calls[-1]["reason"], "episode_ended")
        self.assertEqual([s["hold"] for s in episode.steps], [False, False, False, True, True])
        for snapshot in policy.snapshots[0]:
            np.testing.assert_array_equal(snapshot, np.ones_like(snapshot))
        np.testing.assert_array_equal(episode.actions[3], [0, 0, 0, 0, 0, 0, -1])
        self.assertGreater(overlap_seconds(episode.calls, episode.steps), 0)
        summary = summarize_episodes([episode.record()])
        self.assertEqual(summary["all_calls"]["count"], 2)
        self.assertEqual(summary["filtered_calls"]["count"], 1)
        self.assertEqual(summary["blocking_wait_after_bootstrap_s"], 0)
        self.assertEqual(summary["remote_stage_timings"]["server_inference_s"]["filtered_calls"]["mean_ms"], 20)
        self.assertEqual(summary["remote_stage_timings"]["client_encode_s"]["all_calls"]["missing_count"], 2)

    def test_background_failure_is_propagated_even_at_episode_end(self):
        with self.assertRaisesRegex(RuntimeError, "network failed"):
            self.run_fake(fail=True)


class TimingTests(unittest.TestCase):
    def test_realtime_video_holds_observation_and_keeps_terminal_frame(self):
        episode = AsyncEpisode(True, [np.full((64, 64, 3), v, np.uint8) for v in (0, 50, 100)],
                               [0., .2, .31], [], [], [], [], .31, 0.)
        written = []
        with patch("turbovla.evaluation.async_rollout.imageio.get_writer") as get_writer:
            get_writer.return_value.__enter__.return_value.append_data.side_effect = lambda frame: written.append(frame.copy())
            duration = save_realtime_video(Path("/tmp/async-video-test.mp4"), episode, "blend", fps=20)
        self.assertEqual(len(written), 8)
        self.assertEqual([int(frame[30, 0, 0]) for frame in written], [0, 0, 0, 0, 50, 50, 50, 100])
        self.assertAlmostEqual(duration, .4)
        self.assertLessEqual(duration - episode.rollout_wall_time_s, .1)

    def test_overlap_is_interval_intersection_and_video_marks_background(self):
        calls = [{"start_s": 0, "end_s": 1}, {"start_s": 2, "end_s": 4}]
        steps = [{"action_start_s": 1, "action_end_s": 2.5, "hold": False},
                 {"action_start_s": 3, "action_end_s": 3.5, "hold": True}]
        self.assertEqual(overlap_seconds(calls, steps), 1)
        episode = SimpleNamespace(calls=calls, steps=steps, waits=[{"start_s": 0, "end_s": 1}])
        self.assertEqual(video_phase(episode, .5), "INFERENCE WAIT")
        self.assertEqual(video_phase(episode, 2.2), "CONTROL + BACKGROUND INFERENCE")
        self.assertEqual(video_phase(episode, 3.2), "HOLD / BUFFER EMPTY")
        self.assertEqual(video_phase(episode, 1.5), "CONTROL")


if __name__ == "__main__":
    unittest.main()
