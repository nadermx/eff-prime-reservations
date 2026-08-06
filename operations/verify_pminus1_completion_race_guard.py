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
    end = source.index("\ncompletion_ready=no", start)
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
        queued_evidence = release / "evidence/queued-pminus1-completion-race-guards"
        source_path = release / "scripts/capture_p40_pminus1_completion_M332228177.sh"
    elif base.name == "operations":
        release = base.parent
        evidence = release / "infrastructure/M332228177-completion-race-guard"
        queued_evidence = release / "infrastructure/queued-pminus1-completion-race-guards"
        source_path = base / "capture_p40_pminus1_completion_M332228177.sh"
    else:
        release = base
        evidence = release / "runs/M332228177-completion-race-guard-20260806"
        queued_evidence = release / "runs/queued-pminus1-completion-race-guards-20260806"
        source_path = release / "scripts/capture_p40_pminus1_completion_M332228177.sh"
    source = source_path.read_text()
    subprocess.run(["bash", "-n", str(source_path)], check=True)
    first_receipt_path = evidence / "deployment-receipt.json"
    first_receipt = json.loads(first_receipt_path.read_text())
    second_receipt_path = evidence / "deployment-v2-receipt.json"
    receipt = json.loads(second_receipt_path.read_text())
    faults = json.loads((evidence / "fault-tests.json").read_text())

    assert first_receipt["schema"] == "eff.M332228177-completion-race-guard-deployment.v1"
    assert first_receipt["result"] == "PASS"
    assert first_receipt["source_sha256"] == (
        "49fa4833ae467a03fa46ed7a78d2d0521669660681a0852a9fcaf54de7d0f0b9"
    )
    for name, expected in first_receipt["evidence_sha256"].items():
        assert sha256(evidence / name) == expected
    assert receipt["schema"] == "eff.M332228177-completion-race-guard-deployment.v2"
    assert receipt["result"] == "PASS"
    assert receipt["exponent"] == 332_228_177
    assert receipt["source_sha256"] == sha256(source_path)
    assert receipt["remote_source_sha256"] == receipt["source_sha256"]
    assert receipt["previous_source_sha256"] == first_receipt["source_sha256"]
    assert receipt["predecessor_deployment_receipt_sha256"] == sha256(first_receipt_path)
    assert receipt["arithmetic_restarted"] is False
    assert receipt["arithmetic_signalled"] is False
    assert receipt["completion_path_active_waiting"] is True
    assert receipt["preterminal_negative_gate_exit"] == 64
    assert receipt["gpu_model"] == "Tesla P40"
    assert receipt["gpu_uuid"] == "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
    assert receipt["h200_used"] is False
    for name, expected in receipt["evidence_sha256"].items():
        assert sha256(evidence / name) == expected
    negative = (evidence / "negative-gate-v2.txt").read_text()
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
    assert "systemctl is-active --quiet eff-pm1-m332228177.service" in source
    assert "systemctl is-active --quiet eff-pm1-m332228177-resume.service" in source

    queued = json.loads((queued_evidence / "deployment-receipt.json").read_text())
    assert queued["schema"] == "eff.queued-pminus1-completion-race-guards.v1"
    assert queued["result"] == "PASS"
    assert queued["arithmetic_restarted"] is False
    assert queued["arithmetic_signalled"] is False
    assert queued["h200_used"] is False
    queued_sources = {
        "M332228213-vm101": (
            release / "scripts/capture_p40_pminus1_completion_M332228213.sh"
            if base.name != "operations" else base / "capture_p40_pminus1_completion_M332228213.sh"
        ),
        "M332228447-vm102": (
            release / "scripts/capture_p40_pminus1_completion_M332228447_vm102.sh"
            if base.name != "operations" else base / "capture_p40_pminus1_completion_M332228447_vm102.sh"
        ),
    }
    expected_services = {
        "M332228213-vm101": (
            "eff-pm1-m332228213.service", "eff-pm1-m332228213-resume.service"
        ),
        "M332228447-vm102": (
            "eff-pm1-m332228447-vm102.service",
            "eff-pm1-m332228447-vm102-resume.service",
        ),
    }
    for name, queued_source_path in queued_sources.items():
        lane = queued["lanes"][name]
        queued_source = queued_source_path.read_text()
        subprocess.run(["bash", "-n", str(queued_source_path)], check=True)
        assert queued["source_sha256"][name] == sha256(queued_source_path)
        assert lane["new_source_sha256"] == sha256(queued_source_path)
        assert lane["queued_arithmetic_started"] is False
        assert int(lane["owner_pid_before_after"]) > 1
        assert tuple(lane["queued_services"]) == expected_services[name]
        assert lane["negative_gate_exit"] == 64
        assert "Tesla P40" in (queued_evidence / f"{name}-after.txt").read_text()
        assert "H200" not in (queued_evidence / f"{name}-after.txt").read_text()
        for filename, expected in lane["evidence_sha256"].items():
            assert sha256(queued_evidence / filename) == expected
        assert "exit_code=64" in (
            queued_evidence / f"{name}-negative-gate.txt"
        ).read_text()
        for service in expected_services[name]:
            assert f"systemctl is-active --quiet {service}" in queued_source
        assert '"${terminal_metadata[@]}"' in queued_source
        queued_function = predicate_source(queued_source)
        with tempfile.TemporaryDirectory(prefix="eff-queued-race-verify-") as raw:
            root = Path(raw)
            touch(root / "exit_status.txt", "0\n")
            assert not evaluate(root, queued_function)
            touch(root / "ended_utc.txt")
            assert not evaluate(root, queued_function)
            touch(root / "after_gpu.csv")
            assert evaluate(root, queued_function)
    print("PASS terminal classifier rejects stale/missing final metadata and accepts both settled run paths")
    print("PASS same-PID P40 deployment plus inactive candidate-2/3 completion-path hardening")
    print("SCOPE: result-preservation hardening only; no factor or primality result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
