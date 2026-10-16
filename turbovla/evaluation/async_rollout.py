"""Experimental action scheduling; no model changes and no hooks into the normal evaluator."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math
from pathlib import Path
import time

import imageio
import numpy as np
from PIL import Image, ImageDraw


MODES = ("sync", "replace", "blend")


class ActionTimeline:
    """Actions indexed by actual environment control step, never by HTTP wall time."""

    def __init__(self):
        self.actions = {}
        self.origins = {}

    def merge(self, chunk, observation_step, current_step, mode, blend_steps):
        chunk = np.asarray(chunk, dtype=np.float32)
        if chunk.ndim != 2 or chunk.shape[1] != 7 or not np.isfinite(chunk).all():
            raise ValueError("Expected a finite [horizon, 7] action chunk")
        if mode not in MODES or blend_steps < 1 or current_step < observation_step:
            raise ValueError("Invalid merge settings or backwards control time")
        skipped = min(current_step - observation_step, len(chunk))
        for step in list(self.actions):
            if step < current_step:
                self.actions.pop(step)
                self.origins.pop(step)
        event = {"observation_step": observation_step, "apply_step": current_step,
                 "discarded_prefix_actions": skipped, "expired": skipped == len(chunk),
                 "blended_steps": 0, "old_new_first_arm_disagreement_l2": None}
        if event["expired"]:
            return event
        remaining = chunk[skipped:]
        overlap = 0
        while overlap < min(blend_steps, len(remaining)) and current_step + overlap in self.actions:
            overlap += 1
        if current_step in self.actions:
            event["old_new_first_arm_disagreement_l2"] = float(np.linalg.norm(
                self.actions[current_step][:6] - remaining[0, :6]))
        new_actions, origins = {}, {}
        for index, new in enumerate(remaining):
            step = current_step + index
            action = new.copy()
            oldest_origin = observation_step
            if mode == "blend" and index < overlap:
                alpha = (index + 1) / overlap
                old = self.actions[step]
                action[:6] = (1 - alpha) * old[:6] + alpha * new[:6]
                # Gripper is categorical. Do not invent intermediate commands.
                action[6] = new[6] if alpha >= 0.5 else old[6]
                if alpha < 1:
                    oldest_origin = min(oldest_origin, self.origins[step])
                event["blended_steps"] += 1
            new_actions[step] = action
            origins[step] = oldest_origin
        # A new prediction supersedes the old future, including its tail.
        self.actions, self.origins = new_actions, origins
        return event

    def pop(self, step):
        action = self.actions.pop(step, None)
        origin = self.origins.pop(step, None)
        return action, origin


@dataclass
class AsyncEpisode:
    success: bool
    frames: list
    frame_timestamps_s: list
    actions: list
    steps: list
    calls: list
    waits: list
    rollout_wall_time_s: float
    drain_wall_time_s: float

    def record(self):
        return {"success": self.success, "executed_steps": len(self.actions),
                "executed_actions": self.actions, "step_timings": self.steps,
                "inference_timings": self.calls, "blocking_waits": self.waits,
                "rollout_wall_time_s": self.rollout_wall_time_s,
                "drain_wall_time_s": self.drain_wall_time_s}


def run_episode(cfg, env, policy, instruction, initial_state, mode, *,
                replan_every_steps=4, blend_steps=3, control_hz=20.0, extra_delay_s=0.0,
                max_steps=None):
    from vla_adapter.rollout import TASK_MAX_STEPS
    from turbovla.evaluation.policy import rotate_libero_image, state_from_libero_obs
    from turbovla.evaluation.suite_policy import get_libero_dummy_action

    if mode not in MODES or cfg.control_mode != "relative":
        raise ValueError("This experiment supports sync/replace/blend with relative actions only")
    if not 1 <= replan_every_steps < cfg.chunk_size or not 1 <= blend_steps <= cfg.chunk_size:
        raise ValueError("Require 1 <= replan interval < horizon and 1 <= blend window <= horizon")
    if control_hz <= 0 or extra_delay_s < 0:
        raise ValueError("Require positive control_hz and nonnegative extra_delay_s")
    env.reset()
    obs = env.set_init_state(initial_state)
    for _ in range(cfg.num_steps_wait):
        obs, _, _, _ = env.step(get_libero_dummy_action())
    timeline = ActionTimeline()
    frames, timestamps, actions, steps, calls, waits = [], [], [], [], [], []
    pending = None
    last_submit = -cfg.chunk_size
    last_action = np.asarray(get_libero_dummy_action(), dtype=np.float32)
    start = time.perf_counter()
    next_tick = start
    success = False
    finish = start
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="async-policy")

    def submit(step, primary, wrist):
        # Environment buffers can be reused by env.step: snapshot all inputs.
        state = state_from_libero_obs(obs).copy()
        submitted = time.perf_counter() - start
        primary, wrist = primary.copy(), wrist.copy()
        def predict():
            begun = time.perf_counter()
            if extra_delay_s:
                time.sleep(extra_delay_s)
            policy_start = time.perf_counter()
            prediction = policy.predict_env_action_chunk(
                primary, wrist, instruction, state, execute_steps=cfg.chunk_size)
            ended = time.perf_counter()
            prediction = np.asarray(prediction, dtype=np.float32).copy()
            if prediction.shape != (cfg.chunk_size, 7) or not np.isfinite(prediction).all():
                raise ValueError("Policy returned an invalid action chunk")
            return prediction, {"observation_step": step, "submitted_s": submitted,
                "start_s": begun - start, "end_s": ended - start,
                "duration_s": ended - begun, "policy_duration_s": ended - policy_start,
                "injected_delay_s": extra_delay_s, "remote": dict(getattr(policy, "last_timing", {}))}
        return executor.submit(predict)

    def consume(future, step, apply=True):
        prediction, record = future.result()  # Propagate failures; never use stale actions silently.
        if apply:
            record.update(timeline.merge(prediction, record["observation_step"], step, mode, blend_steps))
            record["applied"] = not record["expired"]
            record["reason"] = "expired" if record["expired"] else "merged"
        else:
            record.update(applied=False, reason="episode_ended", apply_step=None,
                          expired=False, blended_steps=0, discarded_prefix_actions=0)
        calls.append(record)
        return record

    try:
        for step in range(max_steps if max_steps is not None else TASK_MAX_STEPS[cfg.task_suite_name]):
            if step:
                time.sleep(max(0.0, next_tick - time.perf_counter()))
            primary = rotate_libero_image(obs["agentview_image"])
            wrist = rotate_libero_image(obs["robot0_eye_in_hand_image"])
            timestamps.append(time.perf_counter() - start)
            frames.append(np.concatenate([primary, wrist], axis=1))
            merged = False
            if pending is not None and pending.done():
                completed = pending
                pending = None
                merged = consume(completed, step)["applied"]
            needs_plan = step not in timeline.actions
            if step == 0 or (mode == "sync" and needs_plan):
                pending = submit(step, primary, wrist)
                last_submit = step
                wait_start = time.perf_counter() - start
                completed = pending
                pending = None
                merged = consume(completed, step)["applied"]
                waits.append({"start_s": wait_start, "end_s": time.perf_counter() - start,
                              "step": step, "kind": "bootstrap" if step == 0 else "sync"})
            elif mode != "sync" and pending is None and (step - last_submit >= replan_every_steps or needs_plan):
                pending = submit(step, primary, wrist)
                last_submit = step
            action, origin = timeline.pop(step)
            hold = action is None
            if hold:
                action = np.zeros(7, dtype=np.float32)
                action[6] = last_action[6]  # No repeated movement; retain the gripper command.
            action_start = time.perf_counter()
            previous = last_action if actions else None
            obs, _, done, _ = env.step(action.tolist())
            action_end = time.perf_counter()
            steps.append({"step": step, "action_start_s": action_start - start,
                "action_end_s": action_end - start, "env_step_s": action_end - action_start,
                "control_lateness_s": max(0.0, action_start - next_tick) if step else 0.0,
                "hold": hold, "background_pending_at_action_start": pending is not None,
                "merged_before_action": merged, "buffer_remaining": len(timeline.actions),
                "oldest_observation_age_steps": step - origin if origin is not None else None,
                "arm_action_change_l2": float(np.linalg.norm(action[:6] - previous[:6])) if previous is not None else None,
                "gripper_changed": bool(action[6] != previous[6]) if previous is not None else False})
            actions.append(action.tolist())
            last_action = action.copy()
            next_tick = action_start + 1 / control_hz  # Never catch up by skipping simulated steps.
            if done:
                success = True
                break
        finish = time.perf_counter()
        if frames:
            frames.append(np.concatenate([rotate_libero_image(obs["agentview_image"]),
                                          rotate_libero_image(obs["robot0_eye_in_hand_image"])], axis=1))
            timestamps.append(finish - start)
    finally:
        drain_start = time.perf_counter()
        try:
            if pending is not None:
                consume(pending, len(actions), apply=False)
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
        drain = time.perf_counter() - drain_start
    calls.sort(key=lambda call: call["submitted_s"])
    return AsyncEpisode(success, frames, timestamps, actions, steps, calls, waits, finish - start, drain)


def overlap_seconds(calls, steps):
    # One worker and sequential env.step calls make these intervals disjoint within each set.
    return sum(max(0.0, min(c["end_s"], s["action_end_s"]) - max(c["start_s"], s["action_start_s"]))
               for c in calls for s in steps)


def video_phase(episode, elapsed):
    if any(w["start_s"] <= elapsed < w["end_s"] for w in episode.waits):
        return "INFERENCE WAIT"
    if any(s["hold"] and s["action_start_s"] <= elapsed < s["action_end_s"] for s in episode.steps):
        return "HOLD / BUFFER EMPTY"
    if any(c["start_s"] <= elapsed < c["end_s"] for c in episode.calls):
        return "CONTROL + BACKGROUND INFERENCE"
    return "CONTROL"


def save_realtime_video(path, episode, mode, fps=20):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = max(1, math.ceil(episode.rollout_wall_time_s * fps))
    frame_index = 0
    with imageio.get_writer(path, fps=fps) as writer:
        for index in range(count + 1):
            elapsed = min(index / fps, episode.rollout_wall_time_s)
            while frame_index + 1 < len(episode.frames) and episode.frame_timestamps_s[frame_index + 1] <= elapsed:
                frame_index += 1
            phase = video_phase(episode, elapsed)
            if index == count:
                frame_index = len(episode.frames) - 1
                phase = "SUCCESS" if episode.success else "END"
            frame = Image.fromarray(episode.frames[frame_index])
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, frame.width, 20), fill="black")
            draw.text((4, 3), f"{mode} {elapsed:.2f}s | {phase}", fill="white")
            writer.append_data(np.asarray(frame))
    return (count + 1) / fps
