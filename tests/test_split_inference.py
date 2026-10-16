from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import torch

from turbovla.split.client import RemoteTurboVLAPolicy
from turbovla.split.protocol import available_codecs, decode_request, encode_request, MAX_REQUEST_BYTES
from turbovla.split.server import InferenceService, PolicyHTTPServer


def metadata():
    return {
        "ready": True, "version": 1, "server_id": "test-server", "precision": "bf16",
        "chunk_size": 12, "checkpoint_name": "test.pth", "action_dim": 7, "state_dim": 8,
        "image_processor": {"image_mean": [0, 0, 0], "image_std": [1, 1, 1], "rescale_factor": 1 / 255},
        "proprio_mean": [0] * 8, "proprio_std": [1] * 8,
    }


class FakePolicy:
    chunk_size = 12

    def predict_normalized_action_chunk_from_tensors(self, pixels, state, instruction):
        self.received = (pixels, state, instruction)
        return np.arange(84, dtype=np.float32).reshape(12, 7)

    def _normalized_row_to_env_action(self, row):
        return row


class SplitInferenceTests(unittest.TestCase):
    def setUp(self):
        self.policy = FakePolicy()
        self.service = InferenceService(self.policy, metadata())
        self.server = PolicyHTTPServer(("127.0.0.1", 0), self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def header(self, precision):
        return {"version": 1, "request_id": "roundtrip", "server_id": "test-server",
                "precision": precision, "instruction": "move the bowl", "execute_steps": 12}

    def test_tensor_transport_is_bit_exact_for_both_precisions(self):
        generator = torch.Generator().manual_seed(7)
        for precision, dtype in (("bf16", torch.bfloat16), ("fp32", torch.float32)):
            pixels = torch.randn((1, 2, 3, 256, 256), generator=generator).to(dtype)
            state = torch.randn((1, 8), generator=generator).to(dtype)
            body, _ = encode_request(self.header(precision), pixels, state)
            header, got_pixels, got_state = decode_request(body)
            self.assertEqual(header, self.header(precision))
            self.assertTrue(torch.equal(got_pixels, pixels))
            self.assertTrue(torch.equal(got_state, state))
            with self.assertRaises(ValueError):
                decode_request(body[:-1])

    def test_all_codecs_preserve_bits_and_reject_truncated_or_extra_payload(self):
        for precision, dtype in (("bf16", torch.bfloat16), ("fp32", torch.float32)):
            generator = torch.Generator().manual_seed(42)
            pixels = torch.randn((1, 2, 3, 256, 256), generator=generator).to(dtype)
            state = torch.tensor([[0., -0., 1., -1., 0.125, -0.125, 3., 4.]], dtype=dtype)
            for codec in available_codecs():
                with self.subTest(precision=precision, codec=codec):
                    header = {**self.header(precision), "compression": codec}
                    body, _ = encode_request(header, pixels, state)
                    got_header, got_pixels, got_state = decode_request(body)
                    self.assertEqual(got_header, header)
                    self.assertTrue(torch.equal(got_pixels.view(torch.uint8), pixels.view(torch.uint8)))
                    self.assertTrue(torch.equal(got_state.view(torch.uint8), state.view(torch.uint8)))
                    for invalid in (body[:-1], body + b"extra"):
                        with self.assertRaises(ValueError):
                            decode_request(invalid)
            for value in (float("nan"), float("inf"), -float("inf")):
                state[0, 0] = value
                with self.assertRaises(ValueError):
                    encode_request(self.header(precision), pixels, state)

    def test_keepalive_reuses_one_connection_and_can_be_disabled(self):
        image = np.zeros((256, 256, 3), np.uint8)
        for keepalive, expected_connections in ((True, 1), (False, 4)):
            with patch.object(self.server, "get_request", wraps=self.server.get_request) as accept:
                with RemoteTurboVLAPolicy(self.url, keepalive=keepalive) as client:
                    for _ in range(3):
                        client.predict_env_action_chunk(image, image, "move", np.zeros(8, np.float32), 12)
                        self.assertEqual(client.last_timing["connection_reused"], keepalive)
                        self.assertGreaterEqual(client.last_timing["server_receive_s"], 0)
                    self.assertEqual(accept.call_count, expected_connections)

    def test_legacy_codec_negotiation_and_unavailable_codec(self):
        self.service.metadata.pop("transport")
        with RemoteTurboVLAPolicy(self.url) as client:
            self.assertEqual(client.compression, "zlib")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            RemoteTurboVLAPolicy(self.url, compression="lz4_shuffle")

    def test_two_views_preprocessed_on_client_and_actions_return_over_http(self):
        client = RemoteTurboVLAPolicy(self.url)
        image = np.full((256, 256, 3), 128, dtype=np.uint8)
        actions = client.predict_env_action_chunk(image, image, "move the bowl", np.ones(8, np.float32), 5)
        np.testing.assert_array_equal(actions, np.arange(35, dtype=np.float32).reshape(5, 7))
        pixels, state, instruction = self.policy.received
        self.assertEqual(instruction, "move the bowl")
        self.assertTrue(torch.equal(pixels, torch.full_like(pixels, 128 / 255)))
        self.assertTrue(torch.equal(state, torch.ones_like(state)))
        self.assertGreater(client.last_timing["round_trip_s"], 0)
        self.assertLess(client.last_timing["request_bytes"], client.last_timing["uncompressed_tensor_bytes"])

    def test_server_restart_does_not_silently_change_model_mid_episode(self):
        client = RemoteTurboVLAPolicy(self.url)
        self.service.metadata = deepcopy(self.service.metadata)
        self.service.metadata["server_id"] = "new-instance"
        image = np.zeros((256, 256, 3), np.uint8)
        with self.assertRaisesRegex(RuntimeError, "server instance changed"):
            client.predict_env_action_chunk(image, image, "move", np.zeros(8, np.float32), 12)

    def test_optional_server_memory_survives_http_roundtrip(self):
        self.policy.device = torch.device("cuda")
        client = RemoteTurboVLAPolicy(self.url)
        image = np.zeros((256, 256, 3), np.uint8)
        with patch("torch.cuda.max_memory_allocated", return_value=1234), \
             patch("torch.cuda.max_memory_reserved", return_value=5678):
            client.predict_env_action_chunk(image, image, "move", np.zeros(8, np.float32), 12)
        self.assertEqual(client.last_timing["server_cuda_peak_allocated_bytes"], 1234)
        self.assertEqual(client.last_timing["server_cuda_peak_reserved_bytes"], 5678)

    def test_oversized_request_is_rejected_before_reading_payload(self):
        req = Request(self.url + "/predict", data=b"x", headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)})
        with self.assertRaises(HTTPError) as context:
            urlopen(req, timeout=2)
        self.assertEqual(context.exception.code, 413)

    def test_bad_shapes_precision_and_nonfinite_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            RemoteTurboVLAPolicy(self.url, precision="fp32")
        client = RemoteTurboVLAPolicy(self.url)
        image = np.zeros((256, 256, 3), np.uint8)
        with self.assertRaises(ValueError):
            client.predict_env_action_chunk(image, image, "move", np.zeros(7, np.float32))
        with self.assertRaises(ValueError):
            client.predict_env_action_chunk(image, image, "move", np.full(8, np.nan, np.float32))

    def test_disconnected_server_fails_instead_of_using_local_inference(self):
        client = RemoteTurboVLAPolicy(self.url, timeout=0.05)
        self.server.shutdown()
        self.server.server_close()
        # A listener shutdown does not terminate established HTTP/1.1 sockets.
        client.close()
        image = np.zeros((256, 256, 3), np.uint8)
        with self.assertRaisesRegex(RuntimeError, "Thor request failed"):
            client.predict_env_action_chunk(image, image, "move", np.zeros(8, np.float32))


if __name__ == "__main__":
    unittest.main()
