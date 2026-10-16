import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from vla_adapter import rollout


class Clock:
    milliseconds = 0

    def now(self):
        return self.milliseconds / 1000

    def advance(self, milliseconds):
        self.milliseconds += milliseconds


class TimedEnvironment:
    def __init__(self, clock):
        self.clock = clock
        self.steps = 0

    def observation(self):
        frame = np.full((64, 64, 3), self.steps * 10, dtype=np.uint8)
        return {"agentview_image": frame, "robot0_eye_in_hand_image": frame}

    def reset(self):
        self.clock.advance(1000)

    def set_init_state(self, state):
        self.clock.advance(1000)
        return self.observation()

    def step(self, action):
        self.clock.advance(100)
        self.steps += 1
        return self.observation(), 0, self.steps == 5, {}


class TimedPolicy:
    def __init__(self, clock):
        self.clock = clock
        self.calls = 0

    def predict_env_action_chunk(self, *args, execute_steps):
        self.clock.advance(400 if self.calls == 0 else 300)
        self.calls += 1
        return np.zeros((execute_steps, 7), dtype=np.float32)


class VideoTimingTests(unittest.TestCase):
    def record(self):
        clock = Clock()
        env = TimedEnvironment(clock)
        policy = TimedPolicy(clock)
        cfg = rollout.GenerateConfig(num_steps_wait=2, num_open_loop_steps=2)
        with patch.object(rollout.time, "perf_counter", clock.now):
            episode = rollout._run_episode(
                cfg, env, policy, "test instruction", np.zeros(1),
                lambda: [0] * 7, lambda frame: frame,
            )
        return episode

    def test_measured_delays_exclude_reset_and_settling_and_include_last_step(self):
        episode = self.record()
        self.assertTrue(episode.success)
        self.assertEqual(len(episode.executed_actions), 3)
        self.assertAlmostEqual(episode.rollout_wall_time_s, 1.0)
        self.assertEqual([item["step"] for item in episode.inference_timings], [0, 2])
        for actual, expected in zip(episode.inference_timings, [0.4, 0.3]):
            self.assertAlmostEqual(actual["duration_s"], expected)
        for actual, expected in zip(episode.frame_timestamps_s, [0, 0.5, 0.6, 1.0]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(int(episode.frames[-1][30, 0, 0]), 50)

    def test_realtime_export_preserves_waits_and_terminal_observation(self):
        episode = self.record()
        written = []
        with patch.object(rollout.imageio, "get_writer") as get_writer:
            writer = get_writer.return_value.__enter__.return_value
            writer.append_data.side_effect = lambda frame: written.append(frame.copy())
            duration = rollout._save_realtime_video(Path("/tmp/timing-test.mp4"), episode)
        self.assertEqual(len(written), math.ceil(episode.rollout_wall_time_s * 20) + 1)
        self.assertAlmostEqual(duration, len(written) / 20)
        # The first observation must remain on screen throughout the 400 ms inference wait.
        self.assertTrue(all(int(frame[30, 0, 0]) == 20 for frame in written[:8]))
        self.assertEqual(int(written[-1][30, 0, 0]), 50)
        self.assertLessEqual(duration - episode.rollout_wall_time_s, 0.1)
        self.assertGreater(duration, len(episode.executed_actions) / 20)


if __name__ == "__main__":
    unittest.main()
