#!/usr/bin/env python3
"""Verify the complete fail-closed M332228213 P-1/PRP evidence pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


EXPONENT = 332_228_213
EXPECTED_DIGITS = 100_010_658
P40_UUID = "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
PRPLL_SHA = "04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
RESERVATION_SHA = "ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, needle


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    packaged = script_dir.name == "verifiers"
    root = script_dir.parent if packaged else script_dir
    evidence = (
        root / "evidence/post-pminus1-allocation-20260805T2208Z"
        if packaged else
        root / "runs/post-pminus1-allocation-20260805T2208Z"
    )
    receipt = json.loads((evidence / "pipeline-fault-tests.json").read_text())
    staging = json.loads((evidence / "vm101-full-pipeline-staging-v3.json").read_text())

    assert receipt["schema"] == "eff.M332228213-full-pipeline-fault-tests.v1"
    assert receipt["result"] == "PASS"
    assert receipt["candidate"] == {
        "digits": EXPECTED_DIGITS, "exponent": EXPONENT
    }
    assert math.floor(EXPONENT * math.log10(2)) + 1 == EXPECTED_DIGITS
    assert receipt["remote_host"] == "38.86.78.5"
    gpu_policy = receipt["gpu_policy"]
    assert gpu_policy["selected_gpu"] == "Tesla P40"
    assert gpu_policy["h200_used"] is False
    require(gpu_policy["remote_live_state"], P40_UUID, "Tesla P40")
    assert "H200" not in gpu_policy["remote_live_state"]

    assert staging["result"] == "STAGED_NOT_STARTED"
    assert staging["queued_exponent"] == EXPONENT
    assert staging["host"] == "38.86.78.5"
    assert staging["available_disk_bytes"] >= 100_000_000_000
    assert staging["fresh_preflight_directory_exists"] is False
    assert staging["prp_fresh_preflight_directory_exists"] is False
    assert staging["prp_negative_predecessor_gate_exit"] == 64
    assert staging["gpu"]["name"] == "Tesla P40"
    assert staging["gpu"]["uuid"] == P40_UUID
    units = staging["units"]
    for name in (
        "eff-handoff-m332228213.path",
        "eff-handoff-m332228213-prp.path",
        "eff-pm1-m332228213-completion.path",
    ):
        assert units[name]["ActiveState"] == "active"
        assert units[name]["SubState"] == "waiting"
        assert units[name]["UnitFileState"] == "enabled"
    for name in ("eff-pm1-m332228213.service", "eff-prp-m332228213.service"):
        assert units[name]["ActiveState"] == "inactive"
        assert units[name]["SubState"] == "dead"
        assert units[name]["UnitFileState"] == "disabled"

    source_hashes = receipt["source_sha256"]
    for relative, expected in source_hashes.items():
        assert SHA_RE.fullmatch(expected)
        assert digest(root / relative) == expected, relative
    installed = receipt["installed_unit_sha256"]
    for name, expected in installed.items():
        assert expected == digest(root / "configs" / name)
    assert source_hashes["reservation/M332228213.json"] == RESERVATION_SHA
    assert source_hashes["ledger/mersenne_candidates.jsonl"] == (
        receipt["tests"]["append_only_sync"]["verified_final_sha256"]
    )

    staged_map = {
        "/root/eff-prime/runs/M332228213-pminus1-queued/run.sh":
            "scripts/run_p40_pminus1_M332228213.sh",
        "/root/eff-prime/runs/M332228213-pminus1-queued/handoff.sh":
            "scripts/handoff_p40_to_M332228213.sh",
        "/root/eff-prime/runs/M332228213-pminus1-queued/worktodo.original.txt":
            "configs/CUDAPm1_M332228213.worktodo",
        "/root/eff-prime/runs/M332228213-pminus1-queued/reservation/M332228213.json":
            "reservation/M332228213.json",
        "/root/eff-prime/runs/M332228213-pminus1-queued/ledger/mersenne_candidates.jsonl":
            "ledger/mersenne_candidates.jsonl",
        "/root/eff-prime/runs/M332228213-prp-queued/run.sh":
            "scripts/run_p40_prp_M332228213.sh",
        "/root/eff-prime/runs/M332228213-prp-queued/handoff.sh":
            "scripts/handoff_M332228213_pminus1_to_prp.sh",
    }
    for remote_path, local_path in staged_map.items():
        assert staging["staged_hashes"][remote_path] == digest(root / local_path)
    assert staging["staged_hashes"][
        "/root/eff-prime/runs/M332228213-prp-queued/prpll"
    ] == PRPLL_SHA

    tests = receipt["tests"]
    for name in (
        "shell_syntax", "systemd_unit_verification", "candidate_ledger",
        "no_remote_marker_sync_noop", "proof_backup_prelaunch_noop",
    ):
        assert tests[name] == "PASS"
    append = tests["append_only_sync"]
    assert append["records"] >= 20
    assert append["remote_extension_installed"] is True
    assert append["later_local_retained"] is True
    assert append["valid_fork_rejected"] is True
    screening = tests["screening_state_machine"]
    assert screening["no_factor_checkpoint_admits_fresh_status_and_prp_lane"] is True
    assert screening["verified_factor_result_rejects_later_status"] is True
    for timer_name in ("pipeline_sync_timer", "proof_backup_timer"):
        timer = receipt["local_services"][timer_name]
        assert timer["LoadState"] == "loaded"
        assert timer["ActiveState"] == "active"
        assert timer["SubState"] == "waiting"
        assert timer["UnitFileState"] == "enabled"
    prelaunch = receipt["local_services"]["proof_backup_prelaunch_service"]
    assert prelaunch["Result"] == "success"
    assert prelaunch["ExecMainStatus"] == 0

    prp = (root / "scripts/run_p40_prp_M332228213.sh").read_text()
    require(
        prp,
        "expected_exponent=332228213",
        f'expected_gpu_uuid="{P40_UUID}"',
        f'expected_binary_sha256="{PRPLL_SHA}"',
        f'expected_reservation_sha256="{RESERVATION_SHA}"',
        'receipt["classification"] == "completed_no_factor_report"',
        'receipt["b1"] == 1495000 and receipt["b2"] == 32142500',
        "assert 0 <= age <= 900",
        '[item["event"] for item in history[-3:]] == ["checkpoint", "status_snapshot", "lane_started"]',
        'any(item["event"] == "work_started" for item in history[:-3])',
        "pgrep -f '[C]UDAPm1-system-gmp'",
        "minimum_initial_free_bytes=100000000000",
        '-use NO_ASM',
        '-prp "$expected_exponent" -noclean',
    )
    handoff = (root / "scripts/handoff_M332228213_pminus1_to_prp.sh").read_text()
    require(
        handoff,
        'completion-published.txt" ] || fail "P-1 completion is not atomically published"',
        'if [ "$classification" = "verified_factor" ]',
        "assert pow(2, 332228213, q) == 1",
        "NOT_STARTED_VERIFIED_FACTOR.txt",
        '[ "$classification" = "completed_no_factor_report" ]',
        "candidate_preflight.py 332228213",
        "--event status_snapshot --exponent 332228213",
        "--event lane_started --exponent 332228213",
        "./run.sh --preflight-only",
        "systemctl start eff-prp-m332228213.service",
    )
    sync = (root / "tools/sync_vm101_M332228213_pipeline.py").read_text()
    require(
        sync,
        'relation = "remote_extends_local"',
        'relation = "local_already_extends_remote"',
        'raise RuntimeError("remote and local candidate ledgers diverge")',
        'marker": "completion-published.txt"',
        'marker": "NOT_STARTED_VERIFIED_FACTOR.txt"',
        'marker": "completed_utc.txt"',
    )
    proof_wrapper = (
        root / "scripts/backup_vm101_M332228213_prp_proof_residues.sh"
    ).read_text()
    require(
        proof_wrapper,
        'EFF_PROOF_REMOTE_HOST="root@38.86.78.5"',
        'EFF_PROOF_EXPONENT="332228213"',
        'EFF_PROOF_EXPECTED_TOTAL="2048"',
        "systemctl is-active --quiet '$EFF_PROOF_REMOTE_SERVICE'",
        "waiting: VM101 M332228213 PRP proof directory is not active yet",
    )

    assert receipt["scope"].endswith(
        "not a P-1 result, PRP result, primality proof, publication, or EFF claim."
    )
    print(
        "PASS M332228213 full P-1/PRP pipeline: P40-only, both negative "
        "predecessor gates, append-only evidence sync, and proof backup"
    )


if __name__ == "__main__":
    main()
