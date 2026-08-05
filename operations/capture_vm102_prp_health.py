#!/usr/bin/env python3
"""Capture a short-lived, non-secret VM102 PRP health receipt over SSH."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


REMOTE_COMMAND = """set -eu
date -u +%Y-%m-%dT%H:%M:%SZ
systemctl is-active eff-prp-m332228177.service
systemctl show eff-prp-m332228177.service -p NRestarts --value
nvidia-smi --query-gpu=uuid --format=csv,noheader
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--host", default="root@38.86.78.6")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite {args.output}")

    completed = subprocess.run(
        [
            "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=8", args.host, REMOTE_COMMAND,
        ],
        text=True, capture_output=True, check=False, timeout=30,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"SSH health capture failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    lines = completed.stdout.splitlines()
    if len(lines) != 4:
        raise SystemExit(f"expected four health lines; received {len(lines)}")
    fetched_utc, service_state, restarts, gpu_uuid = lines
    receipt = {
        "schema": "eff-vm102-prp-health-v1",
        "fetched_utc": fetched_utc,
        "source_host": args.host,
        "service": "eff-prp-m332228177.service",
        "service_state": service_state,
        "restart_count": int(restarts),
        "gpu_uuid": gpu_uuid,
    }
    if service_state != "active":
        raise SystemExit(f"VM102 PRP state is {service_state!r}, not active")
    if gpu_uuid != "GPU-a5c50372-9b4f-1496-eebf-f7220cd342fd":
        raise SystemExit(f"unexpected VM102 GPU UUID: {gpu_uuid}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
