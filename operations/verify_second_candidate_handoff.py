#!/usr/bin/env python3
"""Replay the finite queued-candidate reservation and staging claims."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    reservation = json.loads((ROOT / "reservation/M332228213.json").read_text())
    require(reservation["candidate"]["exponent"] == 332228213, "reservation exponent")
    require(reservation["candidate"]["decimal_digits"] == 100010658, "digit count")
    require(reservation["reservation_scope"]["exact_exponents_only"] == [332228213], "scope")
    require(
        digest(ROOT / "reservation/M332228213.json")
        == "ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12",
        "reservation digest",
    )
    with (ROOT / "reservation/M332228213.json").open("rb") as signed:
        subprocess.run(
            [
                "ssh-keygen", "-Y", "verify",
                "-f", str(ROOT / "reservation/allowed_signers"),
                "-I", "nadermx", "-n", "eff-prime-reservation",
                "-s", str(ROOT / "reservation/M332228213.json.sig"),
            ],
            stdin=signed,
            stdout=subprocess.DEVNULL,
            check=True,
        )

    snapshot = ROOT / "runs/pre-reservation-M332228213-20260805T2208Z"
    subprocess.run(["sha256sum", "-c", "MANIFEST.sha256"], cwd=snapshot, check=True,
                   stdout=subprocess.DEVNULL)
    preflight = json.loads((snapshot / "preflight.json").read_text())
    require(preflight["eligible_for_manual_reservation_review"] is True, "eligibility")
    require(preflight["assignment_record_present"] is False, "assignment")
    require(preflight["published_status"] == "untested_no_known_factor", "status")
    require(digest(snapshot / "preflight.json") == reservation["fresh_public_status"]["preflight_json_sha256"], "snapshot binding")

    model = json.loads((ROOT / "runs/post-pminus1-allocation-20260805T2208Z/M332228213-pminus1-analysis.json").read_text())
    allocation = json.loads((ROOT / "runs/post-pminus1-allocation-20260805T2208Z/allocation.json").read_text())
    require(model["exponent"] == 332228213, "model exponent")
    require(model["strategies"][0]["b1"] == 1495000, "P-1 B1")
    require(model["strategies"][0]["b2"] == 32142500, "P-1 B2")
    require(allocation["decision"] == "second_candidate_deeper_pminus1_then_prp", "allocation")
    require(allocation["current_candidate_tf"]["modeled_cost_effective"] is False, "TF rejection")
    require(allocation["second_candidate_pminus1"]["modeled_cost_effective"] is True, "P-1 gate")

    subprocess.run(
        ["python3", str(ROOT / "tools/candidate_ledger.py"), "verify", str(ROOT / "ledger/mersenne_candidates.jsonl")],
        check=True, stdout=subprocess.DEVNULL,
    )
    records = [json.loads(line) for line in (ROOT / "ledger/mersenne_candidates.jsonl").read_text().splitlines()]
    history = [item for item in records if item.get("exponent") == 332228213]
    require(history[-1]["event"] == "reservation", "queued candidate must not be marked started")
    require(history[-1]["authority_reference"].endswith("83b3472f12e7d571a6aa43bc478154e42b604289"), "authority")

    staging = json.loads((ROOT / "runs/post-pminus1-allocation-20260805T2208Z/vm101-queued-handoff-staging.json").read_text())
    require(staging["result"] == "STAGED_NOT_STARTED", "staging state")
    require(staging["fresh_preflight_directory_exists"] is False, "fresh status must be deferred")
    require(staging["gpu"]["uuid"] == "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2", "GPU UUID")
    require(staging["units"]["eff-pm1-m332228177-resume.service"]["ActiveState"] == "active", "predecessor active")
    require(staging["units"]["eff-pm1-m332228213.service"]["ActiveState"] == "inactive", "queued arithmetic inactive")
    require(staging["units"]["eff-handoff-m332228213.path"]["ActiveState"] == "active", "handoff watcher")
    require(staging["units"]["eff-prpll-billion-integrity-matrix.path"]["UnitFileState"] == "disabled", "obsolete matrix path")
    require(staging["units"]["eff-tf-m332228177.path"]["UnitFileState"] == "disabled", "uneconomic TF path")

    hashes = staging["staged_hashes"]
    checks = {
        "run.sh": ROOT / "scripts/run_p40_pminus1_M332228213.sh",
        "handoff.sh": ROOT / "scripts/handoff_p40_to_M332228213.sh",
        "worktodo.original.txt": ROOT / "configs/CUDAPm1_M332228213.worktodo",
        "reservation/M332228213.json": ROOT / "reservation/M332228213.json",
        "ledger/mersenne_candidates.jsonl": ROOT / "ledger/mersenne_candidates.jsonl",
    }
    for suffix, local in checks.items():
        remote_hash = next(value for path, value in hashes.items() if path.endswith(suffix))
        require(remote_hash == digest(local), f"staged hash mismatch: {suffix}")

    for script in (
        "scripts/run_p40_pminus1_M332228213.sh",
        "scripts/resume_p40_pminus1_M332228213.sh",
        "scripts/capture_p40_pminus1_completion_M332228213.sh",
        "scripts/handoff_p40_to_M332228213.sh",
    ):
        subprocess.run(["bash", "-n", str(ROOT / script)], check=True)

    print("PASS queued M332228213 reservation, economics, and fail-closed VM101 staging")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
