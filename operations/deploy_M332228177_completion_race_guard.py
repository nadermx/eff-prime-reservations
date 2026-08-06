#!/usr/bin/env python3
"""Atomically harden the live VM101 P-1 completion classifier.

The arithmetic process is not signalled or restarted.  This deployment only
replaces the inactive completion-capture script after binding the live P40,
PID, systemd watcher, and source hashes into an off-host receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOST = "root@38.86.78.5"
RUN = "/root/eff-prime/runs/M332228177-pminus1-20260805T0412Z"
REMOTE = f"{RUN}/capture-completion.sh"
SOURCE = ROOT / "scripts/capture_p40_pminus1_completion_M332228177.sh"
EVIDENCE = ROOT / "runs/M332228177-completion-race-guard-20260806"
OLD_SHA = "3ca39854d4e871273950e9516d2f1e21eaa0776576183f1eeb9447962da29fb2"
GPU_UUID = "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ssh(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST, command],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def snapshot() -> str:
    command = f"""
date -u +%FT%TZ
systemctl show eff-pm1-m332228177-resume.service -p MainPID -p ActiveState -p SubState -p NRestarts --no-pager
systemctl show eff-pm1-m332228177-completion.service -p ActiveState -p SubState -p Result --no-pager
systemctl show eff-pm1-m332228177-completion.path -p ActiveState -p SubState -p UnitFileState --no-pager
printf 'exit_status='; test -f {RUN}/exit_status.txt && cat {RUN}/exit_status.txt || echo absent
printf 'completion_receipt='; test -f {RUN}/completion-receipt.json && echo present || echo absent
pgrep -a -f '[C]UDAPm1-system-gmp'
nvidia-smi --query-gpu=uuid,name,utilization.gpu,memory.used,temperature.gpu --format=csv,noheader
sha256sum {REMOTE}
"""
    return ssh(command).stdout


def main() -> int:
    subprocess.run(["bash", "-n", str(SOURCE)], check=True)
    source_sha = sha256(SOURCE)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    receipt_path = EVIDENCE / "deployment-receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("source_sha256") != source_sha:
            raise RuntimeError("existing deployment receipt binds different source")
        print("existing completion-race-guard deployment receipt is valid")
        return 0

    before = snapshot()
    if GPU_UUID not in before or "Tesla P40" not in before or "H200" in before:
        raise RuntimeError("live arithmetic is not bound to the expected P40")
    if "ActiveState=active\nSubState=running" not in before:
        raise RuntimeError("live P-1 service is not active/running")
    if "ActiveState=active\nSubState=waiting\nUnitFileState=enabled" not in before:
        raise RuntimeError("completion path is not active/waiting/enabled")
    if "exit_status=absent" not in before or "completion_receipt=absent" not in before:
        raise RuntimeError("terminal transition has already begun")
    before_pid = next(
        line.split("=", 1)[1] for line in before.splitlines() if line.startswith("MainPID=")
    )
    before_remote_sha = before.strip().splitlines()[-1].split()[0]
    if before_remote_sha not in {OLD_SHA, source_sha}:
        raise RuntimeError(f"unexpected predeployment remote script hash {before_remote_sha}")

    with tempfile.TemporaryDirectory(prefix="eff-completion-race-") as raw:
        staged = f"{RUN}/.capture-completion.race-guard.tmp"
        subprocess.run(
            ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
             str(SOURCE), f"{HOST}:{staged}"],
            check=True,
        )
        install = ssh(
            f"set -e; test \"$(sha256sum {staged} | awk '{{print $1}}')\" = {source_sha}; "
            f"if test \"$(sha256sum {REMOTE} | awk '{{print $1}}')\" = {OLD_SHA}; then "
            f"cp -p {REMOTE} {REMOTE}.before-race-guard; fi; "
            f"chmod 0755 {staged}; mv {staged} {REMOTE}; sync {REMOTE}; sha256sum {REMOTE}"
        )
        if install.stdout.split()[0] != source_sha:
            raise RuntimeError("atomic install did not produce expected source hash")

    after = snapshot()
    if f"MainPID={before_pid}" not in after:
        raise RuntimeError("arithmetic PID changed during watcher deployment")
    if GPU_UUID not in after or "Tesla P40" not in after or "H200" in after:
        raise RuntimeError("postdeployment P40 binding failed")
    if "exit_status=absent" not in after or "completion_receipt=absent" not in after:
        raise RuntimeError("terminal transition raced the deployment")
    if after.strip().splitlines()[-1].split()[0] != source_sha:
        raise RuntimeError("postdeployment remote hash mismatch")

    negative = ssh(f"cd {RUN} && ./capture-completion.sh", check=False)
    if negative.returncode != 64 or "exit status does not exist" not in negative.stderr:
        raise RuntimeError("preterminal negative gate changed")
    final = snapshot()
    if f"MainPID={before_pid}" not in final or "exit_status=absent" not in final:
        raise RuntimeError("negative gate disturbed arithmetic")

    before_path = EVIDENCE / "vm101-before.txt"
    after_path = EVIDENCE / "vm101-after.txt"
    negative_path = EVIDENCE / "negative-gate.txt"
    before_path.write_text(before)
    after_path.write_text(final)
    negative_path.write_text(
        f"exit_code={negative.returncode}\nstdout={negative.stdout}stderr={negative.stderr}"
    )
    document = {
        "schema": "eff.M332228177-completion-race-guard-deployment.v1",
        "captured_utc": utc_now(),
        "exponent": 332_228_177,
        "source_sha256": source_sha,
        "previous_source_sha256": before_remote_sha,
        "remote_source_sha256": source_sha,
        "arithmetic_pid_before_after": before_pid,
        "arithmetic_restarted": False,
        "arithmetic_signalled": False,
        "gpu_uuid": GPU_UUID,
        "gpu_model": "Tesla P40",
        "h200_used": False,
        "completion_path_active_waiting": True,
        "preterminal_negative_gate_exit": negative.returncode,
        "evidence_sha256": {
            "vm101-before.txt": sha256(before_path),
            "vm101-after.txt": sha256(after_path),
            "negative-gate.txt": sha256(negative_path),
        },
        "result": "PASS",
        "scope": "Terminal-evidence race hardening only; no factor or primality result.",
    }
    temporary = receipt_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, receipt_path)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
