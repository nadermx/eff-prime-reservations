#!/usr/bin/env python3
"""Exercise the exact shell readiness predicate against timestamp races."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/capture_p40_pminus1_completion_M332228177.sh"
OUTPUT = ROOT / "runs/M332228177-completion-race-guard-20260806/fault-tests.json"


def predicate_source() -> str:
    text = SOURCE.read_text()
    start = text.index("completion_metadata_ready() {")
    end = text.index("\n\ncompletion_ready=no", start)
    return text[start:end]


def evaluate(directory: Path, function: str) -> bool:
    completed = subprocess.run(
        ["bash", "-c", f"set -u\n{function}\ncompletion_metadata_ready"],
        cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(completed.stderr)
    return completed.returncode == 0


def touch(path: Path, text: str = "x\n") -> None:
    path.write_text(text)
    now = time.time_ns()
    os.utime(path, ns=(now, now))
    time.sleep(0.002)


def main() -> int:
    subprocess.run(["bash", "-n", str(SOURCE)], check=True)
    text = SOURCE.read_text()
    for required in (
        "resume_ended_utc.txt -nt exit_status.txt",
        "resume_after_gpu.csv -nt exit_status.txt",
        "ended_utc.txt -nt exit_status.txt",
        "after_gpu.csv -nt exit_status.txt",
        "for _ in $(seq 0 30)",
        "terminal process/metadata did not settle",
    ):
        if required not in text:
            raise RuntimeError(f"source omitted race guard: {required}")
    function = predicate_source()
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="eff-race-test-") as raw:
        root = Path(raw)
        touch(root / "resume-checkpoint-metadata.json")
        touch(root / "resume_ended_utc.txt")
        touch(root / "resume_after_gpu.csv")
        touch(root / "exit_status.txt", "0\n")
        results["rejects_stale_resume_metadata"] = not evaluate(root, function)
        touch(root / "resume_ended_utc.txt")
        results["rejects_missing_fresh_resume_telemetry"] = not evaluate(root, function)
        touch(root / "resume_after_gpu.csv")
        results["accepts_settled_resume_metadata"] = evaluate(root, function)

    with tempfile.TemporaryDirectory(prefix="eff-race-test-") as raw:
        root = Path(raw)
        touch(root / "exit_status.txt", "0\n")
        results["rejects_missing_initial_metadata"] = not evaluate(root, function)
        touch(root / "ended_utc.txt")
        results["rejects_missing_initial_telemetry"] = not evaluate(root, function)
        touch(root / "after_gpu.csv")
        results["accepts_settled_initial_metadata"] = evaluate(root, function)

    if not all(results.values()):
        raise RuntimeError(f"race predicate fault test failed: {results}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": "eff.M332228177-completion-race-guard-fault-tests.v1",
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
        "result": "PASS",
        "scope": "Metadata-order fault tests only; no arithmetic result.",
    }
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, OUTPUT)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
