#!/usr/bin/env python3
"""Capture the inactive M332228213 PRP-hit-to-proof deployment."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runs/M332228213-proof-pipeline-20260806T0011Z/deployment-receipt.json"
REMOTE = "root@38.86.78.5"
PRP = "/root/eff-prime/runs/M332228213-prp-queued"
LL = "/root/eff-prime/runs/M332228213-ll-queued"
LOCAL = ROOT / "runs/M332228213-mlucas-queued"
READINESS = ROOT / "runs/mlucas-M332228213-readiness-20260806T0007Z"

SOURCE_FILES = (
    "scripts/run_p40_ll_M332228213.sh",
    "scripts/handoff_M332228213_prp_to_ll.sh",
    "scripts/run_mlucas_ll_M332228213.sh",
    "tools/sync_and_start_M332228213_mlucas.py",
    "tools/capture_second_candidate_proof_pipeline.py",
    "tools/reference_lucas_lehmer_prefix_gmp.c",
    "tools/verify_prpll_result.py",
    "tools/classify_prpll_transition.py",
    "tools/verify_mlucas_result.py",
    "configs/Mlucas_M332228213.cfg",
    "configs/Mlucas_M332228213.worktodo",
    "configs/eff-handoff-m332228213-prp-to-ll.service",
    "configs/eff-handoff-m332228213-prp-to-ll.path",
    "configs/eff-ll-m332228213.service",
    "configs/eff-mlucas-m332228213.service",
    "configs/eff-M332228213-mlucas-trigger.service",
    "configs/eff-M332228213-mlucas-trigger.timer",
    "verify_prpll_result_semantics.py",
    "verify_prp_to_ll_transition.py",
    "verify_mlucas_result_semantics.py",
)

REMOTE_HASH_PATHS = (
    f"{PRP}/prpll",
    f"{PRP}/verify_prpll_result.py",
    f"{PRP}/classify_prpll_transition.py",
    "/root/eff-prime/scripts/handoff_M332228213_prp_to_ll.sh",
    f"{LL}/prpll",
    f"{LL}/run.sh",
    f"{LL}/verify_prpll_result.py",
    "/etc/systemd/system/eff-handoff-m332228213-prp-to-ll.service",
    "/etc/systemd/system/eff-handoff-m332228213-prp-to-ll.path",
    "/etc/systemd/system/eff-ll-m332228213.service",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )


def ssh(command: str) -> subprocess.CompletedProcess[str]:
    return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE, command])


def require(completed: subprocess.CompletedProcess[str], context: str) -> str:
    if completed.returncode != 0:
        raise RuntimeError(f"{context} failed ({completed.returncode}): {completed.stderr.strip()}")
    return completed.stdout


def unit(name: str, *, remote: bool = False, user: bool = False) -> dict[str, object]:
    base = ["systemctl", *(["--user"] if user else []), "show", name, "--no-pager"]
    for prop in ("LoadState", "ActiveState", "SubState", "UnitFileState", "Result", "ExecMainStatus", "NRestarts"):
        base.extend(["-p", prop])
    completed = ssh(" ".join(base)) if remote else run(base)
    values: dict[str, object] = {}
    for line in require(completed, f"unit {name}").splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = int(value) if key in {"ExecMainStatus", "NRestarts"} and value else value
    return values


def remote_hashes() -> dict[str, str]:
    text = require(ssh("sha256sum " + " ".join(REMOTE_HASH_PATHS)), "remote hashes")
    return {path.strip(): value for value, path in (line.split(None, 1) for line in text.splitlines())}


def remote_absent(path: str) -> bool:
    return ssh(f"test ! -e {path}").returncode == 0


def remote_negative(command: str, expected: int) -> dict[str, object]:
    completed = ssh(command)
    if completed.returncode != expected:
        raise RuntimeError(f"negative gate returned {completed.returncode}, expected {expected}")
    return {"exit_status": expected, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def local_negative(command: list[str], expected: int, cwd: Path) -> dict[str, object]:
    completed = run(command, cwd=cwd)
    if completed.returncode != expected:
        raise RuntimeError(f"local negative gate returned {completed.returncode}, expected {expected}")
    return {"exit_status": expected, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def parse_key_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> int:
    for relative in SOURCE_FILES:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(ROOT / relative)
    for relative in (
        "scripts/run_p40_ll_M332228213.sh",
        "scripts/handoff_M332228213_prp_to_ll.sh",
        "scripts/run_mlucas_ll_M332228213.sh",
    ):
        require(run(["bash", "-n", str(ROOT / relative)]), f"syntax {relative}")
    for verifier in (
        "verify_prpll_result_semantics.py",
        "verify_prp_to_ll_transition.py",
        "verify_mlucas_result_semantics.py",
    ):
        output = require(run(["python3", str(ROOT / verifier)]), verifier)
        if "PASS" not in output or "no candidate result or primality claim" not in output:
            raise RuntimeError(f"unexpected verifier scope: {verifier}")

    mlucas_log = (READINESS / "retry-100iters-all-radsets.time").read_text(encoding="utf-8")
    required_residues = (
        "Res64: 212C377C4CC32A57",
        "Res mod 2^35 - 1 =           4446594139",
        "Res mod 2^36 - 1 =          23791397180",
    )
    if mlucas_log.count(required_residues[0]) != 3:
        raise RuntimeError("Mlucas radix-set residue count mismatch")
    for text in required_residues[1:]:
        if mlucas_log.count(text) != 3:
            raise RuntimeError("Mlucas auxiliary residue count mismatch")
    if "3 of 3 radix-sets at FFT length 18432 K passed" not in mlucas_log:
        raise RuntimeError("Mlucas cross-radix acceptance absent")
    gmp = parse_key_values(READINESS / "gmp-prefix-100.stdout")
    if gmp != {
        "exponent": "332228213",
        "iterations": "100",
        "res64": "212C377C4CC32A57",
        "res_mod_2^35_minus_1": "4446594139",
        "res_mod_2^36_minus_1": "23791397180",
        "residue_bits": "332228213",
    }:
        raise RuntimeError("independent GMP prefix mismatch")
    small_prime = require(
        run([str(READINESS / "reference_lucas_lehmer_prefix_gmp"), "31", "29"]),
        "GMP M31 positive control",
    )
    if "res64=0000000000000000" not in small_prime:
        raise RuntimeError("GMP M31 positive control failed")

    remote_units = {
        name: unit(name, remote=True)
        for name in (
            "eff-pm1-m332228177-resume.service",
            "eff-pm1-m332228213.service",
            "eff-prp-m332228213.service",
            "eff-handoff-m332228213-prp-to-ll.path",
            "eff-handoff-m332228213-prp-to-ll.service",
            "eff-ll-m332228213.service",
        )
    }
    gpu = require(ssh(
        "nvidia-smi --query-gpu=name,uuid,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader"
    ), "remote GPU").strip()
    p1_process = require(ssh("ps -eo pid,ppid,lstart,etime,cmd | grep '[C]UDAPm1-system-gmp'"), "live P-1 process").strip()
    p1_progress = require(ssh("tail -n 8 /root/eff-prime/runs/M332228177-pminus1-20260805T0412Z/run.log"), "live P-1 progress").strip()
    deployed = remote_hashes()
    handoff_negative = remote_negative("/root/eff-prime/scripts/handoff_M332228213_prp_to_ll.sh", 75)
    ll_negative = remote_negative(f"cd {LL} && ./run.sh --preflight-only", 64)

    with tempfile.TemporaryDirectory(prefix="eff-M332228213-scp-") as raw:
        temporary = Path(raw)
        require(run([
            "scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            f"{REMOTE}:{LL}/run.sh", f"{REMOTE}:{LL}/verify_prpll_result.py", str(temporary),
        ]), "multiple-source SCP")
        scp_hashes = {path.name: digest(path) for path in sorted(temporary.iterdir())}

    local_units = {
        name: unit(name, user=True)
        for name in (
            "eff-M332228213-mlucas-trigger.timer",
            "eff-M332228213-mlucas-trigger.service",
            "eff-mlucas-m332228213.service",
        )
    }
    trigger = require(run(["python3", str(ROOT / "tools/sync_and_start_M332228213_mlucas.py")]), "local trigger").strip()
    if trigger != "waiting: proof-verified M332228213 probable-prime trigger is absent":
        raise RuntimeError(f"unexpected trigger state: {trigger}")
    mlucas_negative = local_negative([str(LOCAL / "run.sh"), "--preflight-only"], 64, LOCAL)

    receipt = {
        "schema": "eff.M332228213-prp-to-deterministic-proof-pipeline.v1",
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "result": "STAGED_AND_INDEPENDENTLY_PREFIX_VERIFIED_NO_ARITHMETIC_STARTED",
        "candidate": {"exponent": 332228213, "digits": 100010658},
        "source_sha256": {relative: digest(ROOT / relative) for relative in SOURCE_FILES},
        "target_size_readiness": {
            "fft_length_kdoubles": 18432,
            "radix_sets_matched": 3,
            "iterations": 100,
            "res64": "212C377C4CC32A57",
            "res_mod_2_35_minus_1": 4446594139,
            "res_mod_2_36_minus_1": 23791397180,
            "mlucas_log_sha256": digest(READINESS / "retry-100iters-all-radsets.log"),
            "mlucas_time_sha256": digest(READINESS / "retry-100iters-all-radsets.time"),
            "generated_config_sha256": digest(READINESS / "mlucas.cfg"),
            "gmp_source_sha256": digest(ROOT / "tools/reference_lucas_lehmer_prefix_gmp.c"),
            "gmp_binary_sha256": digest(READINESS / "reference_lucas_lehmer_prefix_gmp"),
            "gmp_stdout_sha256": digest(READINESS / "gmp-prefix-100.stdout"),
            "gmp_time_sha256": digest(READINESS / "gmp-prefix-100.time"),
            "gmp_state_sha256": digest(READINESS / "gmp-prefix-100.state"),
            "gmp_state_bytes": (READINESS / "gmp-prefix-100.state").stat().st_size,
            "independent_gmp_match": True,
            "gmp_M31_zero_residue_control": True,
        },
        "vm101": {
            "host": "38.86.78.5",
            "gpu": gpu,
            "h200_used": False,
            "units": remote_units,
            "deployed_sha256": deployed,
            "current_candidate_pminus1_process": p1_process,
            "current_candidate_pminus1_progress": p1_progress,
            "candidate2_pminus1_start_absent": remote_absent("/root/eff-prime/runs/M332228213-pminus1-queued/started_utc.txt"),
            "candidate2_prp_start_absent": remote_absent(f"{PRP}/started_utc.txt"),
            "candidate2_prp_completion_absent": remote_absent(f"{PRP}/completed_utc.txt"),
            "candidate2_probable_prime_trigger_absent": remote_absent(f"{PRP}/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt"),
            "candidate2_ll_completion_absent": remote_absent(f"{LL}/completion-published.txt"),
            "handoff_negative_gate": handoff_negative,
            "ll_negative_gate": ll_negative,
            "multiple_source_scp": {"result": "PASS", "copied_sha256": scp_hashes},
        },
        "local_mlucas": {
            "directory": str(LOCAL),
            "units": local_units,
            "trigger_output": trigger,
            "predecessor_absent": not (LOCAL / "predecessor").exists(),
            "start_absent": not (LOCAL / "started_utc.txt").exists(),
            "completion_absent": not (LOCAL / "completion-published.txt").exists(),
            "negative_gate": mlucas_negative,
            "staged_sha256": {
                name: digest(LOCAL / name)
                for name in (
                    "run.sh", "verify_mlucas_result.py",
                    "Mlucas-main-4a21413-avx2-safe",
                    "Mlucas-main-4a21413-source.tar.gz",
                    "mlucas.cfg", "worktodo.original.txt",
                )
            },
        },
        "tests": {
            "shell_syntax": "PASS",
            "common_result_and_transition_fault_tests": "PASS",
            "target_size_three_radix_match": "PASS",
            "independent_exact_gmp_prefix_match": "PASS",
            "real_absent_predecessor_gates": "PASS",
        },
        "scope": (
            "Candidate 2 proof-path readiness only. M332228213 P-1 and PRP have not "
            "started; there is no probable-prime result, deterministic proof, "
            "independent full confirmation, publication, or EFF claim."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(json.dumps({"output": str(OUTPUT), "sha256": digest(OUTPUT), "result": receipt["result"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        raise SystemExit(1)
