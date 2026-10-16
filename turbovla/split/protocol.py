"""Versioned, bounded tensor transport. No pickle or lossy image compression."""

import json
import math
import struct
import zlib

import numpy as np
import torch

VERSION = 1
PIXEL_SHAPE = (1, 2, 3, 256, 256)
STATE_SHAPE = (1, 8)
MAX_HEADER_BYTES = 16384
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
DTYPES = {"bf16": torch.bfloat16, "fp32": torch.float32}


def validate_header(header):
    if not isinstance(header, dict) or header.get("version") != VERSION:
        raise ValueError("unsupported split-inference protocol version")
    for key in ("request_id", "server_id"):
        if not isinstance(header.get(key), str) or not 1 <= len(header[key]) <= 128:
            raise ValueError(f"invalid {key}")
    if header.get("precision") not in DTYPES:
        raise ValueError("precision must be bf16 or fp32")
    if not isinstance(header.get("instruction"), str) or not 1 <= len(header["instruction"]) <= 4096:
        raise ValueError("instruction must contain 1..4096 characters")
    if type(header.get("execute_steps")) is not int or not 1 <= header["execute_steps"] <= 12:
        raise ValueError("execute_steps must be an integer in 1..12")


def encode_request(header, pixels, state):
    validate_header(header)
    arrays = []
    for tensor, shape in ((pixels, PIXEL_SHAPE), (state, STATE_SHAPE)):
        if tuple(tensor.shape) != shape or tensor.device.type != "cpu":
            raise ValueError(f"expected CPU tensor with shape {shape}")
        tensor = tensor.to(DTYPES[header["precision"]]).contiguous()
        if not torch.isfinite(tensor).all():
            raise ValueError("input tensors must be finite")
        if header["precision"] == "bf16":
            array = tensor.view(torch.uint16).numpy().astype("<u2", copy=False)
        else:
            array = tensor.numpy().astype("<f4", copy=False)
        arrays.append(array.tobytes())
    metadata = json.dumps(header, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(metadata) > MAX_HEADER_BYTES:
        raise ValueError("request header is too large")
    raw = b"".join(arrays)
    body = struct.pack("!I", len(metadata)) + metadata + zlib.compress(raw, level=1)
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("request body is too large")
    return body, len(raw)


def decode_request(body):
    if not 4 < len(body) <= MAX_REQUEST_BYTES:
        raise ValueError("invalid request body length")
    header_size = struct.unpack("!I", body[:4])[0]
    if not 0 < header_size <= MAX_HEADER_BYTES or 4 + header_size >= len(body):
        raise ValueError("invalid header length")
    header = json.loads(body[4:4 + header_size])
    validate_header(header)
    dtype = np.dtype("<u2" if header["precision"] == "bf16" else "<f4")
    pixel_count = math.prod(PIXEL_SHAPE)
    expected = (pixel_count + math.prod(STATE_SHAPE)) * dtype.itemsize
    decoder = zlib.decompressobj()
    raw = decoder.decompress(body[4 + header_size:], max_length=expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("invalid decompressed tensor payload")
    array = np.frombuffer(raw, dtype=dtype).copy()
    tensor = torch.from_numpy(array)
    if header["precision"] == "bf16":
        tensor = tensor.view(torch.bfloat16)
    if not torch.isfinite(tensor).all():
        raise ValueError("input tensors must be finite")
    return header, tensor[:pixel_count].reshape(PIXEL_SHAPE), tensor[pixel_count:].reshape(STATE_SHAPE)
