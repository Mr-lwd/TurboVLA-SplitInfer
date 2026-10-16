"""Thor HTTP service for TurboVLA inference on Orin-preprocessed tensors."""

import argparse
import hashlib
import importlib.metadata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid

import numpy as np

from turbovla.split.protocol import MAX_REQUEST_BYTES, VERSION, available_codecs, decode_request


class InferenceService:
    def __init__(self, policy, metadata):
        self.policy = policy
        self.metadata = metadata
        self.metadata.setdefault("transport", {"codecs": available_codecs(), "keepalive": True})
        self.lock = threading.Lock()

    def predict(self, body):
        start = time.perf_counter()
        header, pixels, state = decode_request(body)
        if header["server_id"] != self.metadata["server_id"]:
            raise ValueError("server instance changed; reconnect the Orin client")
        if header["precision"] != self.metadata["precision"]:
            raise ValueError("tensor precision differs from the loaded model")
        if header["execute_steps"] > self.policy.chunk_size:
            raise ValueError("execute_steps exceeds model horizon")
        decoded = time.perf_counter()
        with self.lock:
            acquired = time.perf_counter()
            pred = self.policy.predict_normalized_action_chunk_from_tensors(pixels, state, header["instruction"])
            actions = np.stack([self.policy._normalized_row_to_env_action(row) for row in pred])
            actions = actions[:header["execute_steps"]].astype(np.float32)
            if actions.shape != (header["execute_steps"], 7) or not np.isfinite(actions).all():
                raise RuntimeError("model returned invalid actions")
            done = time.perf_counter()
            memory = {}
            if getattr(getattr(self.policy, "device", None), "type", None) == "cuda":
                import torch

                memory = {
                    "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(self.policy.device),
                    "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(self.policy.device),
                }
        timing = {
            "decode_s": decoded - start, "queue_s": acquired - decoded,
            "inference_s": done - acquired, "total_s": done - start,
        }
        logging.info(
            "request=%s received_bytes=%d returned_steps=%d inference_ms=%.2f total_ms=%.2f",
            header["request_id"], len(body), len(actions), 1000 * timing["inference_s"], 1000 * timing["total_s"],
        )
        return {
            "version": VERSION, "request_id": header["request_id"],
            "server_id": self.metadata["server_id"], "actions": actions.tolist(), "timing": timing,
            "memory": memory,
        }


class PolicyHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service):
        self.service = service
        super().__init__(address, PolicyRequestHandler)


class PolicyRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(120)
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _json(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            self._json(404, {"error": "unknown endpoint"})
            return
        self._json(200, self.server.service.metadata)

    def do_POST(self):
        if self.path != "/predict":
            self.close_connection = True  # Unread request body cannot be reused.
            self._json(404, {"error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.headers.get("Transfer-Encoding") or not 4 < length <= MAX_REQUEST_BYTES:
                self.close_connection = True
                self._json(413, {"error": "invalid request length; maximum is 2 MiB"})
                return
            receive_start = time.perf_counter()
            body = self.rfile.read(length)
            receive_s = time.perf_counter() - receive_start
            if len(body) != length:
                raise ValueError("incomplete request body")
            result = self.server.service.predict(body)
            result["timing"]["receive_s"] = receive_s
            self._json(200, result)
        except (ValueError, KeyError, TypeError) as error:
            self.close_connection = True
            self._json(400, {"error": str(error)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
            logging.warning("Orin client disconnected or timed out")
        except Exception:
            self.close_connection = True
            logging.exception("Thor inference failed")
            self._json(500, {"error": "Thor inference failed; inspect the server log"})

    def log_message(self, format, *args):
        logging.info("client=%s %s", self.client_address[0], format % args)


def build_metadata(policy):
    import torch
    from turbovla.evaluation.policy import load_preprocessor_config

    config = load_preprocessor_config(policy.dinov3_path)
    checksum = hashlib.sha256()
    with open(policy.ckpt_path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    packages = {}
    for package in ("transformers", "numpy"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    try:
        power = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True, timeout=5)
        power_mode = power.stdout.strip() if power.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        power_mode = None
    return {
        "ready": True, "version": VERSION, "server_id": uuid.uuid4().hex,
        "hostname": socket.gethostname(), "device": str(policy.device),
        "gpu_name": torch.cuda.get_device_name(policy.device) if policy.device.type == "cuda" else "CPU",
        "checkpoint_name": Path(policy.ckpt_path).name, "checkpoint_sha256": checksum.hexdigest(),
        "precision": policy.precision, "chunk_size": policy.chunk_size,
        "action_dim": policy.action_dim, "state_dim": 8,
        "image_processor": {
            "image_mean": config.get("image_mean", [0.485, 0.456, 0.406]),
            "image_std": config.get("image_std", [0.229, 0.224, 0.225]),
            "rescale_factor": config.get("rescale_factor", 1.0 / 255.0),
        },
        "proprio_mean": policy.proprio_mean.tolist(), "proprio_std": policy.proprio_std.tolist(),
        "stats_key": policy.stats_key,
        "split_boundary": "normalized image and state tensors; all neural layers execute on server",
        "runtime": {"python": sys.version, "python_executable": sys.executable,
                    "torch": str(torch.__version__), "cuda": torch.version.cuda,
                    "packages": packages, "platform": platform.platform(), "nvpmodel": power_mode},
        "memory_scope": "PyTorch allocator peak since server process start, including load/warmup and earlier requests; not per rollout or total shared RAM",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ckpt_path", required=True)
    parser.add_argument("--dinov3_path", required=True)
    parser.add_argument("--bert_path", required=True)
    parser.add_argument("--stats_path", default="experiments/libero/configs/libero_all4_stats.json")
    parser.add_argument("--stats_key", default="libero_all4_no_noops")
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--warmup_steps", type=int, default=3)
    args = parser.parse_args()
    if args.warmup_steps < 0:
        parser.error("warmup_steps must be nonnegative")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import torch
    from turbovla.evaluation.suite_policy import TurboVLAPolicy

    if not torch.cuda.is_available():
        raise RuntimeError("Thor server requires a CUDA-capable PyTorch installation")
    policy = TurboVLAPolicy(
        ckpt_path=args.ckpt_path, dinov3_path=args.dinov3_path, bert_path=args.bert_path,
        stats_path=args.stats_path, stats_key=args.stats_key, precision=args.precision,
        allow_hf_download=False, device="cuda",
    )
    if policy.chunk_size != 12 or policy.action_dim != 7:
        raise ValueError("split protocol v1 requires the LIBERO model with 12x7 actions")
    # Warmup is outside measured episodes; real instructions may still have first-call overhead.
    for _ in range(args.warmup_steps):
        policy.predict_normalized_action_chunk_from_tensors(
            torch.zeros((1, 2, 3, 256, 256), dtype=policy.model_dtype),
            torch.zeros((1, 8), dtype=policy.model_dtype),
            "pick up the black bowl between the plate and the ramekin and place it on the plate",
        )
    metadata = build_metadata(policy)
    metadata["warmup_steps"] = args.warmup_steps
    with PolicyHTTPServer((args.host, args.port), InferenceService(policy, metadata)) as server:
        logging.info("READY http://%s:%d GPU=%s server_id=%s", args.host, args.port,
                     metadata["gpu_name"], metadata["server_id"])
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Stopping Thor policy server")


if __name__ == "__main__":
    main()
