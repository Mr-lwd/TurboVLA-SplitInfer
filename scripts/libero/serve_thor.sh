#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
exec "${TURBOVLA_PYTHON:-$HOME/anaconda3/envs/turbovla/bin/python}" -u -m turbovla.split.server \
  --host "${THOR_HOST:-192.168.123.38}" \
  --port "${THOR_PORT:-8765}" \
  --ckpt_path pretrained/TurboVLA/checkpoints/libero/turbovla_libero.pth \
  --dinov3_path "${DINOV3_PATH:-$HOME/models/DINOv3}" \
  --bert_path "${BERT_PATH:-$HOME/models/bert-base-uncased}" \
  --stats_path experiments/libero/configs/libero_all4_stats.json \
  --stats_key libero_all4_no_noops \
  --precision bf16 \
  "$@"
