#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
SPLIT_OUTPUT="${SPLIT_OUTPUT:-outputs/evaluation/split_thor}"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
exec "${TURBOVLA_PYTHON:-$HOME/anaconda3/envs/turbovla-libero/bin/python}" experiments/libero/evaluate.py \
  --remote_policy_url "${THOR_URL:-http://192.168.123.38:8765}" \
  --libero_root "${LIBERO_ROOT:-$REPO_ROOT/../LIBERO}" \
  --task_suite_name libero_spatial \
  --num_trials_per_task 1 \
  --chunk_size 12 \
  --num_open_loop_steps 12 \
  --precision bf16 \
  --seed 7 \
  --mujoco_gl egl \
  --pyopengl_platform egl \
  --save_video true \
  --save_realtime_video true \
  --video_out_path "$SPLIT_OUTPUT/videos" \
  --result_json_path "$SPLIT_OUTPUT/libero_spatial.json" \
  --log_path "$SPLIT_OUTPUT/libero_spatial.log" \
  "$@"
