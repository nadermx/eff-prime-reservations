#!/usr/bin/env python3
"""Atomically harden inactive candidate-2/3 P-1 completion classifiers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "runs/queued-pminus1-completion-race-guards-20260806"
LANES = (
    {
        "name": "M332228213-vm101",
        "host": "root@38.86.78.5",
        "ip": "38.86.78.5",
        "run": "/root/eff-prime/runs/M332228213-pminus1-queued",
        "source": ROOT / "scripts/capture_p40_pminus1_completion_M332228213.sh",
        "old_sha": "b438e604f06fe9796ef8d0cb5d3ad0d337679439022f987994eb1e8e9128a1d3",
        "units": ("eff-pm1-m332228213.service", "eff-pm1-m332228213-resume.service"),
        "owner": "eff-pm1-m332228177-resume.service",
        "gpu_uuid": "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2",
    },
    {
        "name": "M332228447-vm102",
        "host": "root@38.86.78.6",
        "ip": "38.86.78.6",
        "run": "/root/eff-prime/runs/M332228447-pminus1-factor-branch",
        "source": ROOT / "scripts/capture_p40_pminus1_completion_M332228447_vm102.sh",
        "old_sha": "30f54204a74eb43c18fe035eb35c94724c9f4d9cb4ec60fc60d3fbf18081fb7f",
        "units": (
            "eff-pm1-m332228447-vm102.service",
            "eff-pm1-m332228447-vm102-resume.service",
        ),
        "owner": "eff-prp-m332228177.service",
        "gpu_uuid": "GPU-a5c50372-9b4f-1496-eebf-f7220cd342fd",
    },
)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ssh(lane: dict[str, object], command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         str(lane["host"]), command],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def snapshot(lane: dict[str, object]) -> str:
    units = " ".join(str(x) for x in lane["units"])
    run = str(lane["run"])
    return ssh(lane, f"""
date -u +%FT%TZ
systemctl show {lane['owner']} -p Id -p MainPID -p ActiveState -p SubState -p NRestarts --no-pager
systemctl show {units} -p Id -p ActiveState -p SubState -p UnitFileState --no-pager
printf 'exit_status='; test -f {run}/exit_status.txt && cat {run}/exit_status.txt || echo absent
printf 'completion_receipt='; test -f {run}/completion-receipt.json && echo present || echo absent
nvidia-smi --query-gpu=uuid,name,utilization.gpu,memory.used,temperature.gpu --format=csv,noheader
sha256sum {run}/capture-completion.sh
""").stdout


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    receipt_path = EVIDENCE / "deployment-receipt.json"
    source_hashes = {str(lane["name"]): sha256(Path(lane["source"])) for lane in LANES}
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("source_sha256") != source_hashes:
            raise RuntimeError("existing queued-guard receipt binds different sources")
        print("existing queued completion-race-guard receipt is valid")
        return 0

    lane_receipts: dict[str, object] = {}
    for lane in LANES:
        source = Path(lane["source"])
        subprocess.run(["bash", "-n", str(source)], check=True)
        expected_new = source_hashes[str(lane["name"])]
        before = snapshot(lane)
        if str(lane["gpu_uuid"]) not in before or "Tesla P40" not in before or "H200" in before:
            raise RuntimeError(f"{lane['name']}: wrong live GPU owner")
        owner_pid = next(
            line.split("=", 1)[1] for line in before.splitlines() if line.startswith("MainPID=")
        )
        if not owner_pid.isdigit() or int(owner_pid) <= 1:
            raise RuntimeError(f"{lane['name']}: owner service has no PID")
        for unit in lane["units"]:
            block_start = before.index(f"Id={unit}")
            block = before[block_start:block_start + 180]
            if "ActiveState=inactive" not in block or "SubState=dead" not in block:
                raise RuntimeError(f"{lane['name']}: queued arithmetic is not inactive")
        if "exit_status=absent" not in before or "completion_receipt=absent" not in before:
            raise RuntimeError(f"{lane['name']}: queued lane already has attempt/result state")
        current_sha = before.strip().splitlines()[-1].split()[0]
        if current_sha != lane["old_sha"]:
            raise RuntimeError(f"{lane['name']}: unexpected old source {current_sha}")

        run = str(lane["run"])
        staged = f"{run}/.capture-completion.race-guard.tmp"
        subprocess.run(
            ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
             str(source), f"{lane['host']}:{staged}"], check=True,
        )
        installed = ssh(
            lane,
            f"set -e; test \"$(sha256sum {staged} | awk '{{print $1}}')\" = {expected_new}; "
            f"cp -p {run}/capture-completion.sh {run}/capture-completion.sh.before-race-guard; "
            f"chmod 0755 {staged}; mv {staged} {run}/capture-completion.sh; "
            f"sync {run}/capture-completion.sh; sha256sum {run}/capture-completion.sh",
        )
        if installed.stdout.split()[0] != expected_new:
            raise RuntimeError(f"{lane['name']}: installed source mismatch")
        negative = ssh(lane, f"cd {run} && ./capture-completion.sh", check=False)
        if negative.returncode != 64 or "missing exit status" not in negative.stderr:
            raise RuntimeError(f"{lane['name']}: preterminal negative gate changed")
        after = snapshot(lane)
        if f"MainPID={owner_pid}" not in after:
            raise RuntimeError(f"{lane['name']}: owner arithmetic PID changed")
        if after.strip().splitlines()[-1].split()[0] != expected_new:
            raise RuntimeError(f"{lane['name']}: postdeployment source mismatch")
        before_path = EVIDENCE / f"{lane['name']}-before.txt"
        after_path = EVIDENCE / f"{lane['name']}-after.txt"
        negative_path = EVIDENCE / f"{lane['name']}-negative-gate.txt"
        before_path.write_text(before)
        after_path.write_text(after)
        negative_path.write_text(
            f"exit_code={negative.returncode}\nstdout={negative.stdout}stderr={negative.stderr}"
        )
        lane_receipts[str(lane["name"])] = {
            "remote_host": lane["ip"],
            "gpu_uuid": lane["gpu_uuid"],
            "owner_service": lane["owner"],
            "owner_pid_before_after": owner_pid,
            "queued_services": list(lane["units"]),
            "queued_arithmetic_started": False,
            "old_source_sha256": lane["old_sha"],
            "new_source_sha256": expected_new,
            "negative_gate_exit": negative.returncode,
            "evidence_sha256": {
                before_path.name: sha256(before_path),
                after_path.name: sha256(after_path),
                negative_path.name: sha256(negative_path),
            },
        }

    document = {
        "schema": "eff.queued-pminus1-completion-race-guards.v1",
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_sha256": source_hashes,
        "lanes": lane_receipts,
        "arithmetic_restarted": False,
        "arithmetic_signalled": False,
        "h200_used": False,
        "result": "PASS",
        "scope": "Inactive terminal-path hardening only; no candidate arithmetic or result.",
    }
    temporary = receipt_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, receipt_path)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
