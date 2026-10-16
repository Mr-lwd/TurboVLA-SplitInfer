"""Lightweight Orin policy: preprocess locally and receive actions from Thor."""

import json
from http.client import HTTPConnection, HTTPException
import time
import uuid
from urllib.parse import urlsplit

import numpy as np
import torch

from turbovla.evaluation.policy import _build_manual_rgb_normalizer, state_from_libero_obs
from turbovla.split.protocol import DTYPES, MAX_RESPONSE_BYTES, VERSION, available_codecs, encode_request


class RemoteTurboVLAPolicy:
    def __init__(self, url, timeout=120.0, precision="bf16", chunk_size=12, compression="auto", keepalive=True):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("remote_policy_url must be an HTTP URL without credentials")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("remote_policy_url must contain only scheme, host and port")
        if timeout <= 0:
            raise ValueError("remote_timeout_s must be positive")
        self.url = url.rstrip("/")
        self.timeout = timeout
        # HTTPConnection bypasses proxies, reuses TCP and enables TCP_NODELAY.
        self.connection = HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
        self.keepalive = keepalive
        self.last_http_timing = {}
        self.server_info = self._request("/health")
        info = self.server_info
        if info.get("version") != VERSION or not info.get("ready"):
            self.close()
            raise RuntimeError("Thor server is not ready or uses an incompatible protocol")
        if info.get("precision") != precision or info.get("chunk_size") != chunk_size:
            self.close()
            raise ValueError("client precision/chunk_size must match the Thor server")
        common = set(available_codecs()) & set(info.get("transport", {}).get("codecs", ["zlib"]))
        if compression == "auto":
            compression = next((c for c in ("zstd_shuffle", "lz4_shuffle", "zlib_shuffle", "zlib") if c in common), None)
        if compression not in common:
            self.close()
            raise ValueError(f"Compression {compression!r} unavailable on both devices; common codecs: {sorted(common)}")
        self.compression = compression
        self.precision = precision
        self.chunk_size = chunk_size
        self.checkpoint_name = info["checkpoint_name"]
        processor = info["image_processor"]
        self.processor = _build_manual_rgb_normalizer(
            processor["image_mean"], processor["image_std"], processor["rescale_factor"],
            expected_size=256, patch_size=16, backbone_name="split DINOv3",
        )
        self.state_mean = np.asarray(info["proprio_mean"], dtype=np.float32)
        self.state_std = np.asarray(info["proprio_std"], dtype=np.float32)
        if self.state_mean.shape != (8,) or self.state_std.shape != (8,) or np.any(self.state_std < 0):
            raise ValueError("server returned invalid state normalization statistics")
        self.last_timing = {}

    def _request(self, path, body=None):
        start = time.perf_counter()
        reused = self.connection.sock is not None
        try:
            self.connection.request("POST" if body is not None else "GET", path, body=body,
                                    headers={"Content-Type": "application/octet-stream",
                                             "Connection": "keep-alive" if self.keepalive else "close"})
            sent = time.perf_counter()
            response = self.connection.getresponse()
            headers_received = time.perf_counter()
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise RuntimeError("Thor response exceeded the size limit")
            if response.status != 200:
                raise RuntimeError(f"Thor HTTP {response.status}: {payload[:4096].decode('utf-8', errors='replace')}")
            result = json.loads(payload)
            self.last_http_timing = {
                "client_request_send_s": sent - start,
                "client_response_wait_s": headers_received - sent,
                "client_response_read_s": time.perf_counter() - headers_received,
                "connection_reused": reused,
            }
            return result
        except (HTTPException, TimeoutError, OSError) as error:
            self.close()
            # Never replay a POST automatically: the server may already have run it.
            raise RuntimeError(f"Thor request failed at {self.url}: {error}") from error
        except Exception:
            self.close()
            raise
        finally:
            if not self.keepalive:
                self.close()

    def close(self):
        self.connection.close()

    def __del__(self):
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def predict_env_action_chunk(self, primary_image, wrist_image, instruction, state_or_obs, execute_steps=None):
        self.last_timing = {}
        start = time.perf_counter()
        state = state_from_libero_obs(state_or_obs) if isinstance(state_or_obs, dict) else np.asarray(
            state_or_obs, dtype=np.float32
        )
        if state.shape != (8,):
            raise ValueError("state must have 8 elements")
        pixels = self.processor([primary_image, wrist_image])["pixel_values"].unsqueeze(0)
        normalized_state = torch.from_numpy((state - self.state_mean) / (self.state_std + 1e-6)).unsqueeze(0)
        pixels = pixels.to(DTYPES[self.precision])
        normalized_state = normalized_state.to(DTYPES[self.precision])
        prepared = time.perf_counter()
        steps = self.chunk_size if execute_steps is None else execute_steps
        request_id = uuid.uuid4().hex
        header = {
            "version": VERSION, "request_id": request_id, "server_id": self.server_info["server_id"],
            "precision": self.precision, "instruction": instruction, "execute_steps": steps,
        }
        # Keep the original header compatible with older zlib-only servers.
        if self.compression != "zlib":
            header["compression"] = self.compression
        body, raw_bytes = encode_request(header, pixels, normalized_state)
        encoded = time.perf_counter()
        response = self._request("/predict", body)
        received = time.perf_counter()
        if response.get("request_id") != request_id or response.get("server_id") != header["server_id"]:
            raise RuntimeError("Thor returned actions for a different request or server instance")
        actions = np.asarray(response["actions"], dtype=np.float32)
        if actions.shape != (steps, 7) or not np.isfinite(actions).all():
            raise RuntimeError(f"Thor returned invalid actions: shape={actions.shape}")
        server_timing = response["timing"]
        self.last_timing = {
            "request_id": request_id,
            "client_preprocess_s": prepared - start,
            "client_encode_s": encoded - prepared,
            "round_trip_s": received - encoded,
            "server_decode_s": server_timing["decode_s"],
            "server_queue_s": server_timing["queue_s"],
            "server_inference_s": server_timing["inference_s"],
            "server_total_s": server_timing["total_s"],
            # This residual includes HTTP/socket/response overhead; it is not pure wire latency.
            "transport_overhead_s": max(0.0, received - encoded - server_timing["total_s"]),
            "request_bytes": len(body), "uncompressed_tensor_bytes": raw_bytes,
            "compression": self.compression,
            **self.last_http_timing,
        }
        if "receive_s" in server_timing:
            self.last_timing["server_receive_s"] = server_timing["receive_s"]
        # Optional in protocol v1: older servers simply omit allocator metrics.
        for key, value in response.get("memory", {}).items():
            if key in {"cuda_peak_allocated_bytes", "cuda_peak_reserved_bytes"}:
                self.last_timing[f"server_{key}"] = value
        return actions
