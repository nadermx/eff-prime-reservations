#!/usr/bin/env python3
"""Verify the compact audit record for VM102 PRP proof-residue backups."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


EXPONENT = 332_228_177
PROOF_POWER = 11
EXPECTED_TOTAL = 1 << PROOF_POWER
EXPECTED_BYTES = 41_528_528
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_RE = re.compile(r"^([0-9a-f]{64})  ([1-9][0-9]*)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return parsed.replace(tzinfo=timezone.utc)


def proof_points(exponent: int, power: int) -> set[int]:
    """Reproduce gpuowl ProofSet's exact retained-iteration construction."""
    points = [0]
    span = (exponent + 1) // 2
    for _ in range(power):
        points.extend(point + span for point in list(points))
        span = (span + 1) // 2
    assert len(points) == 1 << power
    points[0] = exponent
    return set(points)


def records_match_manifest(records: list[dict[str, object]], text: str) -> bool:
    expected: list[tuple[int, str]] = []
    seen: set[int] = set()
    valid_points = proof_points(EXPONENT, PROOF_POWER)
    for record in records:
        if set(record) not in (
            {
                "captured_utc", "iteration", "bytes", "sha256",
                "remote_host", "stable_remote_before_after",
            },
            {
                "captured_utc", "iteration", "bytes", "sha256",
                "remote_host", "stable_remote_before_after",
                "recovered_after_interrupted_commit",
            },
        ):
            return False
        iteration = record.get("iteration")
        digest = record.get("sha256")
        if not isinstance(iteration, int) or isinstance(iteration, bool):
            return False
        if iteration in seen or iteration not in valid_points:
            return False
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            return False
        if record.get("bytes") != EXPECTED_BYTES:
            return False
        if record.get("remote_host") != "38.86.78.6":
            return False
        if record.get("stable_remote_before_after") is not True:
            return False
        if "recovered_after_interrupted_commit" in record and (
            record["recovered_after_interrupted_commit"] is not True
        ):
            return False
        try:
            parse_utc(str(record["captured_utc"]))
        except (KeyError, TypeError, ValueError):
            return False
        seen.add(iteration)
        expected.append((iteration, digest))

    manifest: list[tuple[int, str]] = []
    for line in text.splitlines():
        match = MANIFEST_RE.fullmatch(line)
        if match is None:
            return False
        manifest.append((int(match.group(2)), match.group(1)))
    return manifest == sorted(expected)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    packaged = script_dir.name == "verifiers"
    release = script_dir.parent if packaged else script_dir
    if packaged:
        evidence = release / "evidence" / "prp-proof-residue-backup"
        residue_manifest = evidence / "RESIDUE_MANIFEST.sha256"
    else:
        evidence = (
            release / "runs" / "M332228177-prp-20260805T0450Z" /
            "proof-residues-off-vm"
        )
        residue_manifest = evidence / "MANIFEST.sha256"

    receipt_path = evidence / "backup-receipt.json"
    ledger_path = evidence / "proof-residue-ledger.jsonl"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    manifest_text = residue_manifest.read_text(encoding="utf-8")

    assert receipt["schema"] == "eff.vm102-prp-proof-residue-backup.v1"
    assert receipt["result"] == "PASS"
    assert receipt["exponent"] == EXPONENT
    assert receipt["proof_power"] == PROOF_POWER
    assert receipt["expected_total_residues"] == EXPECTED_TOTAL
    assert receipt["expected_residue_bytes"] == EXPECTED_BYTES
    count = receipt["off_vm_backed_up_count"]
    assert isinstance(count, int) and 1 <= count <= EXPECTED_TOTAL
    assert count == len(records) == len(manifest_text.splitlines())
    assert receipt["off_vm_backed_up_bytes"] == count * EXPECTED_BYTES
    assert 0 <= receipt["remote_eligible_count"] <= count
    assert 0 <= receipt["copied_this_run"] <= count
    assert sha256(residue_manifest) == receipt["manifest_sha256"]
    assert sha256(ledger_path) == receipt["ledger_sha256"]
    assert records_match_manifest(records, manifest_text)

    backup_script = release / "scripts" / "backup_vm102_prp_proof_residues.sh"
    service_unit = release / "configs" / "eff-vm102-proof-residue-backup.service"
    timer_unit = release / "configs" / "eff-vm102-proof-residue-backup.timer"
    assert sha256(backup_script) == receipt["backup_script_sha256"]
    assert sha256(service_unit) == receipt["installed_service_unit_sha256"]
    assert sha256(timer_unit) == receipt["installed_timer_unit_sha256"]
    assert "OnUnitActiveSec=10min" in timer_unit.read_text(encoding="utf-8")
    assert "Persistent=true" in timer_unit.read_text(encoding="utf-8")
    assert "backup_vm102_prp_proof_residues.sh" in service_unit.read_text(
        encoding="utf-8"
    )

    captured = parse_utc(receipt["captured_utc"])
    last_scrub = parse_utc(receipt["last_full_scrub_utc"])
    elapsed = int((captured - last_scrub).total_seconds())
    assert receipt["full_scrub_interval_seconds"] == 21_600
    assert 0 <= receipt["seconds_since_full_scrub"] <= 21_600
    assert receipt["seconds_since_full_scrub"] <= elapsed <= (
        receipt["seconds_since_full_scrub"] + 60
    )
    assert receipt["remote_service"] == {
        "active_state": "active", "sub_state": "running", "restarts": 0
    }
    assert receipt["scope"] == (
        "Immutable PRP proof residues only; not a PRP result or primality proof."
    )

    timer_state = (evidence / "timer-state.txt").read_text(encoding="utf-8")
    assert "timer_active_state=active" in timer_state
    assert "timer_sub_state=waiting" in timer_state
    assert "timer_unit_file_state=enabled" in timer_state
    assert "last_service_result=success" in timer_state
    assert "last_service_exec_main_status=0" in timer_state
    assert f"backup_script_sha256={sha256(backup_script)}" in timer_state
    assert f"service_unit_sha256={sha256(service_unit)}" in timer_state
    assert f"timer_unit_sha256={sha256(timer_unit)}" in timer_state
    assert f"verifier_sha256={sha256(Path(__file__))}" in timer_state

    claim_path = (
        release / "status" / "claim_status.json"
        if packaged else release / "claim_status.json"
    )
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    assert claim["candidate_prp_proof_power"] == PROOF_POWER
    assert claim["candidate_prp_expected_proof_residue_count"] == EXPECTED_TOTAL
    assert 1 <= claim["candidate_prp_completed_proof_residues_off_vm"] <= count
    assert claim["candidate_prp_proof_residue_backup_timer_enabled"] is True
    assert claim["candidate_prp_proof_residue_full_content_verification_passed"] is True
    assert claim["candidate_prp_proof_residue_tamper_test_rejected"] is True
    assert claim[
        "candidate_prp_bulky_proof_residue_corpus_excluded_from_shareable_package"
    ] is True
    assert claim["candidate_prp_result_obtained"] is False
    assert claim["deterministic_primality_proof_completed"] is False

    # The shareable package intentionally omits the eventual ~85 GB corpus.
    # Root-mode callers can request a complete content scrub explicitly.
    if not packaged and os.environ.get("EFF_VERIFY_BULKY_PROOF_RESIDUES") == "1":
        for record in records:
            path = evidence / str(record["iteration"])
            assert path.stat().st_size == EXPECTED_BYTES
            assert sha256(path) == record["sha256"]

    tampered = copy.deepcopy(records)
    tampered[0]["sha256"] = "0" * 64
    assert not records_match_manifest(tampered, manifest_text)
    print(
        "verified VM102 proof-residue backup: "
        f"{count}/{EXPECTED_TOTAL} residues, "
        f"{receipt['off_vm_backed_up_bytes']} bytes; tamper rejected"
    )


if __name__ == "__main__":
    main()
