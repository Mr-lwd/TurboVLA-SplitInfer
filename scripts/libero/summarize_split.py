"""Export reports from an existing split result, without contacting either device."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.libero.benchmark_local import device_label, summarize, write_json, write_reports


def export_result(source, output_root=None, client_device="unknown_client", exclude_first_calls=1):
    source = Path(source).expanduser().resolve()
    raw = source.read_bytes()
    result = json.loads(raw)
    if result.get("policy_backend") != "remote":
        raise ValueError("Expected a split/remote evaluation result")
    summary, rows = summarize(result, exclude_first_calls)
    server = result.get("remote_server") or {}
    server_tag = device_label(server.get("gpu_name", ""), "", server.get("hostname", "unknown_server"))
    client_tag = re.sub(r"[^a-z0-9_-]+", "_", client_device.lower()).strip("_") or "unknown_client"
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
    suite = re.sub(r"[^a-zA-Z0-9_-]+", "_", result["task_suite_name"])
    name = f"{client_tag}_to_{server_tag}_split_{suite}_backfill_{stamp}"
    root = Path(output_root).expanduser().resolve() if output_root else source.parent / "reports"
    directory = root / name
    directory.mkdir(parents=True, exist_ok=False)
    prefix = directory / name
    metadata_path = prefix.with_name(name + "_metadata.json")
    metadata = {
        "status": "backfilled", "exported_at": stamp, "source_result": str(source),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "client_device_label": client_tag, "client_device_label_source": "user supplied; not inferred from export machine",
        "original_recorded_metadata": {key: value for key, value in result.items() if key != "tasks"},
        "exclude_first_calls_per_episode": exclude_first_calls,
        "client_runtime": None, "client_cuda_peak_allocated_bytes": None,
        "client_cuda_peak_reserved_bytes": None, "evaluation_process_wall_time_s": None,
        "server_runtime": server.get("runtime"),
        "unavailable_note": "Unrecorded original runtime/config/memory data cannot be reconstructed. Export time is not evaluation time. No new inference was run.",
    }
    summary.update(source_result=str(source), metadata_path=str(metadata_path), device_name=client_tag)
    write_json(metadata_path, metadata)
    write_reports(prefix, summary, rows)
    return prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output_root", "--output-root", type=Path)
    parser.add_argument("--client_device", "--client-device", default="unknown_client",
                        help="Original client device label, e.g. orin; defaults to unknown")
    parser.add_argument("--exclude_first_calls", "--exclude-first-calls", type=int, default=1)
    args = parser.parse_args()
    prefix = export_result(args.input, args.output_root, args.client_device, args.exclude_first_calls)
    print(f"Saved reports: {prefix.parent}")


if __name__ == "__main__":
    main()
