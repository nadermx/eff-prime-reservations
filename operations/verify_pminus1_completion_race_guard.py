#!/usr/bin/env python3
"""Verify the live M332228177 terminal-evidence race hardening offline."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def predicate_source(source: str) -> str:
    start = source.index("completion_metadata_ready() {")
    end = source.index("\n\ncompletion_ready=no", start)
    return source[start:end]


def evaluate(directory: Path, function: str) -> bool:
    completed = subprocess.run(
        ["bash", "-c", f"set -u\n{function}\ncompletion_metadata_ready"],
        cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert completed.returncode in {0, 1}, completed.stderr
    return completed.returncode == 0


def touch(path: Path, text: str = "x\n") -> None:
    path.write_text(text)
    now = time.time_ns()
    os.utime(path, ns=(now, now))
    time.sleep(0.002)


def main() -> int:
    base = Path(__file__).resolve().parent
    if base.name == "verifiers":
        release = base.parent
        evidence = release / "evidence/M332228177-completion-race-guard"
        source_path = release / "scripts/capture_p40_pminus1_completion_M332228177.sh"
    elif base.name == "operations":
        release = base.parent
        evidence = release / "infrastructure/M332228177-completion-race-guard"
        source_path = base / "capture_p40_pminus1_completion_M332228177.sh"
    else:
        release = base
        evidence = release / "runs/M332228177-completion-race-guard-20260806"
        source_path = release / "scripts/capture_p40_pminus1_completion_M332228177.sh"
    source = source_path.read_text()
    subprocess.run(["bash", "-n", str(source_path)], check=True)
    receipt = json.loads((evidence / "deployment-receipt.json").read_text())
    faults = json.loads((evidence / "fault-tests.json").read_text())

    assert receipt["schema"] == "eff.M332228177-completion-race-guard-deployment.v1"
    assert receipt["result"] == "PASS"
    assert receipt["exponent"] == 332_228_177
    assert receipt["source_sha256"] == sha256(source_path)
    assert receipt["remote_source_sha256"] == receipt["source_sha256"]
    assert receipt["previous_source_sha256"] == (
        "3ca39854d4e871273950e9516d2f1e21eaa0776576183f1eeb9447962da29fb2"
    )
    assert receipt["arithmetic_restarted"] is False
    assert receipt["arithmetic_signalled"] is False
    assert receipt["completion_path_active_waiting"] is True
    assert receipt["preterminal_negative_gate_exit"] == 64
    assert receipt["gpu_model"] == "Tesla P40"
    assert receipt["gpu_uuid"] == "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
    assert receipt["h200_used"] is False
    for name, expected in receipt["evidence_sha256"].items():
        assert sha256(evidence / name) == expected
    negative = (evidence / "negative-gate.txt").read_text()
    assert "exit_code=64" in negative
    assert "exit status does not exist" in negative

    assert faults["schema"] == "eff.M332228177-completion-race-guard-fault-tests.v1"
    assert faults["result"] == "PASS"
    assert all(faults["results"].values())
    function = predicate_source(source)
    with tempfile.TemporaryDirectory(prefix="eff-race-verify-") as raw:
        root = Path(raw)
        touch(root / "resume-checkpoint-metadata.json")
        touch(root / "resume_ended_utc.txt")
        touch(root / "resume_after_gpu.csv")
        touch(root / "exit_status.txt", "0\n")
        assert not evaluate(root, function)
        touch(root / "resume_ended_utc.txt")
        assert not evaluate(root, function)
        touch(root / "resume_after_gpu.csv")
        assert evaluate(root, function)
    with tempfile.TemporaryDirectory(prefix="eff-race-verify-") as raw:
        root = Path(raw)
        touch(root / "exit_status.txt", "0\n")
        assert not evaluate(root, function)
        touch(root / "ended_utc.txt")
        assert not evaluate(root, function)
        touch(root / "after_gpu.csv")
        assert evaluate(root, function)

    assert "systemctl start" not in source
    assert "-prp" not in source and "-ll" not in source
    print("PASS terminal classifier rejects stale/missing final metadata and accepts both settled run paths")
    print("PASS same-PID P40 deployment, preterminal refusal, and no-arithmetic-change receipt")
    print("SCOPE: result-preservation hardening only; no factor or primality result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
