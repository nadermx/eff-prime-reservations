#!/usr/bin/env python3
"""Capture reproducible fault tests for the queued M332228213 pipeline."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "runs/post-pminus1-allocation-20260805T2208Z" /
    "pipeline-fault-tests.json"
)
REMOTE = "root@38.86.78.5"
REMOTE_IP = "38.86.78.5"

SHELL_SCRIPTS = (
    "scripts/run_p40_pminus1_M332228213.sh",
    "scripts/resume_p40_pminus1_M332228213.sh",
    "scripts/capture_p40_pminus1_completion_M332228213.sh",
    "scripts/handoff_p40_to_M332228213.sh",
    "scripts/run_p40_prp_M332228213.sh",
    "scripts/handoff_M332228213_pminus1_to_prp.sh",
    "scripts/backup_vm102_prp_proof_residues.sh",
    "scripts/backup_vm101_M332228213_prp_proof_residues.sh",
)

UNITS = (
    "configs/eff-pm1-m332228213.service",
    "configs/eff-pm1-m332228213-resume.service",
    "configs/eff-pm1-m332228213-completion.service",
    "configs/eff-pm1-m332228213-completion.path",
    "configs/eff-handoff-m332228213.service",
    "configs/eff-handoff-m332228213.path",
    "configs/eff-prp-m332228213.service",
    "configs/eff-handoff-m332228213-prp.service",
    "configs/eff-handoff-m332228213-prp.path",
    "configs/eff-vm101-M332228213-pipeline-sync.service",
    "configs/eff-vm101-M332228213-pipeline-sync.timer",
    "configs/eff-vm101-M332228213-proof-residue-backup.service",
    "configs/eff-vm101-M332228213-proof-residue-backup.timer",
    "configs/eff-M332228177-pminus1-prp-guard.service",
    "configs/eff-M332228177-pminus1-prp-guard.timer",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def load_sync_module():
    path = ROOT / "tools/sync_vm101_M332228213_pipeline.py"
    spec = importlib.util.spec_from_file_location("eff_pipeline_sync", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pipeline synchronizer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_ledger_reconciliation() -> dict[str, object]:
    module = load_sync_module()
    source = ROOT / "ledger/mersenne_candidates.jsonl"
    lines = source.read_bytes().splitlines(keepends=True)
    if len(lines) < 2:
        raise RuntimeError("candidate ledger is too short for prefix tests")
    with tempfile.TemporaryDirectory(
        prefix="pipeline-ledger-test-", dir=ROOT / "runs"
    ) as raw:
        test_root = Path(raw)
        (test_root / "tools").mkdir()
        (test_root / "ledger").mkdir()
        shutil.copy2(
            ROOT / "tools/candidate_ledger.py",
            test_root / "tools/candidate_ledger.py",
        )
        local = test_root / "ledger/mersenne_candidates.jsonl"
        remote = test_root / "remote.jsonl"

        local.write_bytes(b"".join(lines[:-1]))
        remote.write_bytes(b"".join(lines))
        relation, final_hash = module.reconcile_global_ledger(test_root, remote)
        if relation != "remote_extends_local" or local.read_bytes() != source.read_bytes():
            raise RuntimeError("valid remote extension was not installed")

        local.write_bytes(b"".join(lines))
        remote.write_bytes(b"".join(lines[:-1]))
        relation, _ = module.reconcile_global_ledger(test_root, remote)
        if relation != "local_already_extends_remote":
            raise RuntimeError("valid later local ledger was not retained")

        # Build two individually valid children of the same chain head.  The
        # synchronizer must reject the fork even though both ledgers verify.
        local.write_bytes(source.read_bytes())
        remote.write_bytes(source.read_bytes())
        append_base = [
            "python3", str(test_root / "tools/candidate_ledger.py"), "append",
        ]
        subprocess.run(
            append_base + [str(local), "--event", "status_snapshot",
                           "--exponent", "332228213", "--evidence-sha256",
                           "1" * 64, "--note", "fixture local child",
                           "--timestamp", "2026-08-05T22:40:00Z"],
            check=True, stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            append_base + [str(remote), "--event", "status_snapshot",
                           "--exponent", "332228213", "--evidence-sha256",
                           "2" * 64, "--note", "fixture remote child",
                           "--timestamp", "2026-08-05T22:40:01Z"],
            check=True, stdout=subprocess.DEVNULL,
        )
        try:
            module.reconcile_global_ledger(test_root, remote)
        except RuntimeError:
            fork_rejected = True
        else:
            fork_rejected = False
        if not fork_rejected:
            raise RuntimeError("valid divergent remote ledger was accepted")
    return {
        "records": len(lines),
        "remote_extension_installed": True,
        "later_local_retained": True,
        "valid_fork_rejected": True,
        "verified_final_sha256": final_hash,
    }


def exercise_screening_transitions() -> dict[str, object]:
    """Prove no-factor remains nonterminal while a factor is terminal."""
    source = ROOT / "ledger/mersenne_candidates.jsonl"
    authority = (
        "https://github.com/nadermx/eff-prime-reservations/commit/"
        "83b3472f12e7d571a6aa43bc478154e42b604289"
    )
    with tempfile.TemporaryDirectory(
        prefix="screening-ledger-test-", dir=ROOT / "runs"
    ) as raw:
        work = Path(raw)
        tool = ROOT / "tools/candidate_ledger.py"
        started = work / "started.jsonl"
        shutil.copy2(source, started)

        def append(path: Path, event: str, evidence: str, timestamp: str,
                   *, authority_reference: str | None = None,
                   expect_success: bool = True) -> subprocess.CompletedProcess[str]:
            command = [
                "python3", str(tool), "append", str(path), "--event", event,
                "--exponent", "332228213", "--evidence-sha256", evidence,
                "--note", f"fixture {event}", "--timestamp", timestamp,
            ]
            if authority_reference is not None:
                command.extend(["--authority-reference", authority_reference])
            return subprocess.run(
                command, text=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=expect_success,
            )

        append(started, "status_snapshot", "3" * 64, "2026-08-05T22:55:00Z")
        append(
            started, "work_started", "3" * 64, "2026-08-05T22:55:01Z",
            authority_reference=authority,
        )
        no_factor = work / "no-factor.jsonl"
        factor = work / "factor.jsonl"
        shutil.copy2(started, no_factor)
        shutil.copy2(started, factor)

        append(no_factor, "checkpoint", "4" * 64, "2026-08-05T22:55:02Z")
        append(no_factor, "status_snapshot", "5" * 64, "2026-08-05T22:55:03Z")
        append(
            no_factor, "lane_started", "5" * 64, "2026-08-05T22:55:04Z",
            authority_reference=authority,
        )
        run(["python3", str(tool), "verify", str(no_factor)])

        append(factor, "result", "6" * 64, "2026-08-05T22:55:02Z")
        blocked = append(
            factor, "status_snapshot", "7" * 64, "2026-08-05T22:55:03Z",
            expect_success=False,
        )
        if blocked.returncode == 0:
            raise RuntimeError("terminal factor result admitted a later lane")
        run(["python3", str(tool), "verify", str(factor)])
    return {
        "no_factor_checkpoint_admits_fresh_status_and_prp_lane": True,
        "verified_factor_result_rejects_later_status": True,
    }


def exercise_cross_candidate_ordering() -> dict[str, object]:
    """Verify one canonical chain for both predecessor outcomes."""
    source = ROOT / "ledger/mersenne_candidates.jsonl"
    tool = ROOT / "tools/candidate_ledger.py"
    authority = (
        "https://github.com/nadermx/eff-prime-reservations/commit/"
        "83b3472f12e7d571a6aa43bc478154e42b604289"
    )
    for predecessor_event in ("checkpoint", "result"):
        with tempfile.TemporaryDirectory(
            prefix=f"ordered-{predecessor_event}-", dir=ROOT / "runs"
        ) as raw:
            ledger = Path(raw) / "ledger.jsonl"
            shutil.copy2(source, ledger)

            def append(event: str, exponent: int, evidence: str, timestamp: str,
                       authority_reference: str | None = None) -> None:
                command = [
                    "python3", str(tool), "append", str(ledger), "--event", event,
                    "--exponent", str(exponent), "--evidence-sha256", evidence,
                    "--note", "cross-candidate ordering fixture",
                    "--timestamp", timestamp,
                ]
                if authority_reference:
                    command.extend(["--authority-reference", authority_reference])
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL)

            append(predecessor_event, 332228177, "8" * 64, "2026-08-05T23:05:00Z")
            append("status_snapshot", 332228213, "9" * 64, "2026-08-05T23:05:01Z")
            append(
                "work_started", 332228213, "9" * 64,
                "2026-08-05T23:05:02Z", authority,
            )
            run(["python3", str(tool), "verify", str(ledger)])
    return {
        "no_factor_checkpoint_then_second_start": True,
        "factor_result_then_second_start": True,
        "single_writer": "VM101",
    }


def user_unit(name: str) -> dict[str, object]:
    result = run([
        "systemctl", "--user", "show", name, "--no-pager",
        "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
        "-p", "UnitFileState", "-p", "Result", "-p", "ExecMainStatus",
    ])
    values: dict[str, object] = {}
    for line in result.stdout.splitlines():
        key, value = line.split("=", 1)
        values[key] = int(value) if key == "ExecMainStatus" and value else value
    return values


def main() -> int:
    for relative in SHELL_SCRIPTS:
        run(["bash", "-n", str(ROOT / relative)])
    run(["systemd-analyze", "verify", *(str(ROOT / item) for item in UNITS)])
    run(["python3", str(ROOT / "tools/candidate_ledger.py"), "verify",
         str(ROOT / "ledger/mersenne_candidates.jsonl")])

    sync = run(["python3", str(ROOT / "tools/sync_vm101_M332228213_pipeline.py")])
    if sync.stdout.strip() != "no completed remote stage to sync":
        raise RuntimeError(f"unexpected pre-handoff sync state: {sync.stdout!r}")
    proof_wait = run([
        "/bin/bash", str(ROOT / "scripts/backup_vm101_M332228213_prp_proof_residues.sh")
    ])
    expected_wait = "waiting: VM101 M332228213 PRP proof directory is not active yet"
    if proof_wait.stdout.strip() != expected_wait:
        raise RuntimeError(f"unexpected proof prelaunch state: {proof_wait.stdout!r}")
    factor_guard = run([
        "python3", str(ROOT / "tools/guard_vm102_prp_after_M332228177_pminus1.py")
    ])
    expected_guard = "waiting: M332228177 P-1 terminal receipt is not published"
    if factor_guard.stdout.strip() != expected_guard:
        raise RuntimeError(f"unexpected terminal factor-guard state: {factor_guard.stdout!r}")

    ledger_tests = exercise_ledger_reconciliation()
    sync_timer = user_unit("eff-vm101-M332228213-pipeline-sync.timer")
    proof_timer = user_unit("eff-vm101-M332228213-proof-residue-backup.timer")
    proof_service = user_unit("eff-vm101-M332228213-proof-residue-backup.service")
    factor_guard_timer = user_unit("eff-M332228177-pminus1-prp-guard.timer")
    factor_guard_service = user_unit("eff-M332228177-pminus1-prp-guard.service")
    for timer in (sync_timer, proof_timer, factor_guard_timer):
        if timer.get("ActiveState") != "active" or timer.get("SubState") != "waiting":
            raise RuntimeError(f"required local timer is not waiting: {timer}")
        if timer.get("UnitFileState") != "enabled":
            raise RuntimeError(f"required local timer is not enabled: {timer}")
    if proof_service.get("Result") != "success" or proof_service.get("ExecMainStatus") != 0:
        raise RuntimeError("proof prelaunch service did not exit successfully")
    if factor_guard_service.get("Result") != "success" or factor_guard_service.get(
        "ExecMainStatus"
    ) != 0:
        raise RuntimeError("verified-factor guard preterminal service did not exit successfully")

    remote = run([
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE,
        "systemctl show eff-pm1-m332228177-resume.service "
        "eff-handoff-m332228213.path eff-handoff-m332228213-prp.path "
        "eff-pm1-m332228213.service eff-prp-m332228213.service "
        "-p Id -p ActiveState -p SubState -p NRestarts --no-pager; "
        "nvidia-smi --query-gpu=uuid,name,utilization.gpu,memory.used,temperature.gpu "
        "--format=csv,noheader",
    ])
    if "Tesla P40" not in remote.stdout or "H200" in remote.stdout:
        raise RuntimeError("queued pipeline is not bound exclusively to the selected P40")
    for required in (
        "Id=eff-pm1-m332228177-resume.service\nActiveState=active\nSubState=running",
        "Id=eff-handoff-m332228213.path\nActiveState=active\nSubState=waiting",
        "Id=eff-handoff-m332228213-prp.path\nActiveState=active\nSubState=waiting",
        "Id=eff-pm1-m332228213.service\nActiveState=inactive\nSubState=dead",
        "Id=eff-prp-m332228213.service\nActiveState=inactive\nSubState=dead",
    ):
        if required not in remote.stdout:
            raise RuntimeError(f"unexpected remote service state; missing {required!r}")

    hashes = {
        relative: digest(ROOT / relative)
        for relative in (
            *SHELL_SCRIPTS,
            *UNITS,
            "tools/sync_vm101_M332228213_pipeline.py",
            "tools/guard_vm102_prp_after_M332228177_pminus1.py",
            "tools/candidate_ledger.py",
            "reservation/M332228213.json",
            "reservation/M332228213.json.sig",
            "ledger/mersenne_candidates.jsonl",
        )
    }
    installed = {
        name: digest(Path("/home/john/.config/systemd/user") / name)
        for name in (
            "eff-vm101-M332228213-pipeline-sync.service",
            "eff-vm101-M332228213-pipeline-sync.timer",
            "eff-vm101-M332228213-proof-residue-backup.service",
            "eff-vm101-M332228213-proof-residue-backup.timer",
            "eff-M332228177-pminus1-prp-guard.service",
            "eff-M332228177-pminus1-prp-guard.timer",
        )
    }
    for name, value in installed.items():
        if value != digest(ROOT / "configs" / name):
            raise RuntimeError(f"installed unit differs from source: {name}")

    receipt = {
        "schema": "eff.M332228213-full-pipeline-fault-tests.v1",
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate": {"exponent": 332228213, "digits": 100010658},
        "remote_host": REMOTE_IP,
        "gpu_policy": {
            "selected_gpu": "Tesla P40",
            "h200_used": False,
            "remote_live_state": remote.stdout,
        },
        "tests": {
            "shell_syntax": "PASS",
            "systemd_unit_verification": "PASS",
            "candidate_ledger": "PASS",
            "no_remote_marker_sync_noop": "PASS",
            "proof_backup_prelaunch_noop": "PASS",
            "append_only_sync": ledger_tests,
            "screening_state_machine": exercise_screening_transitions(),
            "cross_candidate_ledger_ordering": exercise_cross_candidate_ordering(),
            "verified_factor_guard_preterminal_noop": "PASS",
        },
        "local_services": {
            "pipeline_sync_timer": sync_timer,
            "proof_backup_timer": proof_timer,
            "proof_backup_prelaunch_service": proof_service,
            "verified_factor_guard_timer": factor_guard_timer,
            "verified_factor_guard_preterminal_service": factor_guard_service,
        },
        "installed_unit_sha256": installed,
        "source_sha256": hashes,
        "result": "PASS",
        "scope": (
            "Pre-result handoff and evidence fault tests only; not a P-1 result, "
            "PRP result, primality proof, publication, or EFF claim."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"PASS wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
