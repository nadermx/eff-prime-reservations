#!/usr/bin/env python3
"""Synchronize verified VM101 transition evidence into the local release tree.

Only marker-complete stages are copied. A remote candidate ledger may replace
the local ledger only when it is a byte-for-byte append-only extension. A
later local ledger is retained when it already extends the remote stage copy.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


HOST = "root@38.86.78.5"
P1_REMOTE = "/root/eff-prime/runs/M332228213-pminus1-queued"
PRP_REMOTE = "/root/eff-prime/runs/M332228213-prp-queued"

STAGES = (
    {
        "name": "p1-start",
        "remote": P1_REMOTE,
        "local": "runs/M332228213-pminus1-queued",
        "marker": "handoff_utc.txt",
        "receipt": "sync-p1-start.json",
        "dirs": ("preflight", "predecessor", "ledger"),
        "files": (
            "preflight.stdout", "ledger-status-head.txt", "ledger-work-head.txt",
            "ledger-verify.txt", "handoff-preflight.stdout", "handoff_utc.txt",
            "handoff-provenance.sha256", "handoff-gpu.csv", "started_utc.txt",
            "before_gpu.csv", "input_provenance.sha256",
        ),
    },
    {
        "name": "p1-result",
        "remote": P1_REMOTE,
        "local": "runs/M332228213-pminus1-queued",
        "marker": "completion-published.txt",
        "receipt": "sync-p1-result.json",
        "dirs": ("ledger",),
        "files": (
            "completion-receipt.json", "factor-certificate.json",
            "completion-provenance.sha256", "completion-receipt.sha256",
            "completion-classifier.stdout", "exit_status.txt", "ended_utc.txt",
            "resume_ended_utc.txt", "after_gpu.csv", "resume_after_gpu.csv",
            "completion-published.txt", "ledger-result-head.txt",
            "ledger-result-verify.txt",
        ),
    },
    {
        "name": "prp-factor-stop",
        "remote": PRP_REMOTE,
        "local": "runs/M332228213-prp-queued",
        "marker": "NOT_STARTED_VERIFIED_FACTOR.txt",
        "receipt": "sync-prp-factor-stop.json",
        "dirs": ("ledger",),
        "files": ("NOT_STARTED_VERIFIED_FACTOR.txt",),
    },
    {
        "name": "prp-start",
        "remote": PRP_REMOTE,
        "local": "runs/M332228213-prp-queued",
        "marker": "handoff_utc.txt",
        "receipt": "sync-prp-start.json",
        "dirs": ("preflight", "predecessor", "ledger"),
        "files": (
            "preflight.stdout", "ledger-status-head.txt", "ledger-lane-head.txt",
            "ledger-verify.txt", "handoff-preflight.stdout", "handoff_utc.txt",
            "handoff-provenance.sha256", "handoff-gpu.csv", "started_utc.txt",
            "attempt_started_utc.txt", "before_gpu.csv", "disk_before.txt",
            "input_provenance.sha256", "NOT_STARTED_VERIFIED_FACTOR.txt",
        ),
    },
    {
        "name": "prp-result",
        "remote": PRP_REMOTE,
        "local": "runs/M332228213-prp-queued",
        "marker": "completed_utc.txt",
        "receipt": "sync-prp-result.json",
        "dirs": ("ledger",),
        "files": (
            "validated-result.json", "completed_utc.txt", "attempt_exit_status.txt",
            "attempt_ended_utc.txt", "after_gpu.csv", "disk_after.txt",
        ),
        "mapped_files": (("work/results-0.txt", "results-0.txt"),),
    },
)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def marker_exists(remote: str, marker: str) -> bool:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", HOST,
         "test", "-f", f"{remote}/{marker}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def rsync_remote(remote: str, relative: str, destination: Path,
                 directory: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = f"{HOST}:{remote}/{relative}"
    if directory:
        source += "/"
        destination.mkdir(parents=True, exist_ok=True)
        target = str(destination) + "/"
    else:
        target = str(destination)
    subprocess.run(
        ["rsync", "-a", "--ignore-missing-args", source, target],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def verify_ledger(root: Path, ledger: Path) -> list[bytes]:
    subprocess.run(
        ["python3", str(root / "tools/candidate_ledger.py"), "verify", str(ledger)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return ledger.read_bytes().splitlines(keepends=True)


def reconcile_global_ledger(root: Path, remote_ledger: Path) -> tuple[str, str]:
    global_ledger = root / "ledger/mersenne_candidates.jsonl"
    remote_lines = verify_ledger(root, remote_ledger)
    with global_ledger.open("r+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        local_bytes = stream.read()
        local_lines = local_bytes.splitlines(keepends=True)
        if local_lines == remote_lines[:len(local_lines)]:
            relation = "remote_extends_local"
            if len(remote_lines) > len(local_lines):
                stream.seek(0)
                stream.write(b"".join(remote_lines))
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
        elif remote_lines == local_lines[:len(remote_lines)]:
            relation = "local_already_extends_remote"
        else:
            raise RuntimeError("remote and local candidate ledgers diverge")
        fcntl.flock(stream, fcntl.LOCK_UN)
    verify_ledger(root, global_ledger)
    return relation, sha256(global_ledger)


def copy_stage(root: Path, stage: dict[str, object]) -> bool:
    remote = str(stage["remote"])
    marker = str(stage["marker"])
    local = root / str(stage["local"])
    receipt = local / str(stage["receipt"])
    if receipt.is_file() or not marker_exists(remote, marker):
        return False

    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="M332228213-sync-", dir=runs) as raw_tmp:
        tmp = Path(raw_tmp)
        for relative in stage.get("dirs", ()):
            rsync_remote(remote, str(relative), tmp / str(relative), directory=True)
        for relative in stage.get("files", ()):
            rsync_remote(remote, str(relative), tmp / str(relative))
        for remote_name, local_name in stage.get("mapped_files", ()):
            rsync_remote(remote, str(remote_name), tmp / str(local_name))

        remote_ledger = tmp / "ledger/mersenne_candidates.jsonl"
        if not remote_ledger.is_file():
            raise RuntimeError(f"{stage['name']}: remote ledger missing")
        relation, global_head = reconcile_global_ledger(root, remote_ledger)

        local.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["rsync", "-a", "--exclude", str(stage["receipt"]),
             str(tmp) + "/", str(local) + "/"],
            check=True,
        )
        copied = {
            path.relative_to(local).as_posix(): sha256(path)
            for path in sorted(local.rglob("*"))
            if path.is_file() and path != receipt
        }
        remote_records = [
            json.loads(line) for line in remote_ledger.read_text(encoding="utf-8").splitlines()
        ]
        document = {
            "schema": "eff.vm101-M332228213-pipeline-sync.v1",
            "stage": stage["name"],
            "synced_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "remote_host": "38.86.78.5",
            "remote_directory": remote,
            "remote_marker": marker,
            "ledger_relation": relation,
            "remote_ledger_head": remote_records[-1]["record_sha256"],
            "global_ledger_sha256_after_sync": global_head,
            "copied_files": copied,
            "result": "PASS",
            "scope": "Verified append-only evidence synchronization; not a primality result.",
        }
        with receipt.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--refresh-deliverables", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    lock_path = root / "runs/.M332228213-pipeline-sync.lock"
    lock_path.parent.mkdir(exist_ok=True)
    changed = False
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("pipeline sync already running")
            return 0
        for stage in STAGES:
            if copy_stage(root, stage):
                print(f"synced {stage['name']}")
                changed = True
        if changed and args.refresh_deliverables:
            subprocess.run(["python3", str(root / "refresh_deliverables.py")], check=True)
    print("pipeline sync complete" if changed else "no completed remote stage to sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
