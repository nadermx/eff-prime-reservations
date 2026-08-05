#!/usr/bin/env python3
"""Stop VM102 PRP only after a definitive M332228177 P-1 factor.

No-factor is nonterminal and leaves PRP running.  A factor must survive an
independent modular check before the exact VM102 service can be stopped.
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


ROOT = Path(__file__).resolve().parents[1]
VM101 = "root@38.86.78.5"
VM102 = "root@38.86.78.6"
VM101_IP = "38.86.78.5"
VM102_IP = "38.86.78.6"
EXPONENT = 332_228_177
B1 = 1_495_000
B2 = 32_142_500
P1_RUN = "/root/eff-prime/runs/M332228177-pminus1-20260805T0412Z"
PRP_RUN = "/root/eff-prime/runs/M332228177-prp-20260805T0450Z"
PRP_SERVICE = "eff-prp-m332228177.service"
PRPLL_SHA = "04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
LOCAL = ROOT / "runs/M332228177-pminus1-terminal-guard"
REMOTE_FILES = (
    "completion-receipt.json",
    "completion-receipt.sha256",
    "completion-provenance.sha256",
    "completion-classifier.stdout",
    "completion-captured_utc.txt",
    "exit_status.txt",
    "run.log",
    "run.time",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ssh(host: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def remote_file_exists(host: str, path: str) -> bool:
    return ssh(host, ["test", "-f", path], check=False).returncode == 0


def remote_sha(host: str, path: str) -> str:
    output = ssh(host, ["sha256sum", path]).stdout.strip()
    value = output.split(None, 1)[0]
    if len(value) != 64:
        raise RuntimeError(f"invalid remote SHA-256 for {path}")
    return value


def stable_copy(host: str, remote_path: str, local_path: Path) -> str:
    before = remote_sha(host, remote_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
         f"{host}:{remote_path}", str(local_path)],
        check=True,
    )
    after = remote_sha(host, remote_path)
    local = digest(local_path)
    if before != after or before != local:
        raise RuntimeError(f"unstable or mismatched remote evidence: {remote_path}")
    return local


def verify_factor(exponent: int, factor: int) -> None:
    if factor <= 1 or factor.bit_length() >= exponent:
        raise ValueError("factor is not a proven proper-size divisor")
    if pow(2, exponent, factor) != 1:
        raise ValueError("factor fails independent 2**p mod q == 1 check")


def decision_for_receipt(receipt: dict[str, object]) -> str:
    if receipt.get("exponent") != EXPONENT:
        raise ValueError("wrong receipt exponent")
    if receipt.get("b1") != B1 or receipt.get("b2") != B2:
        raise ValueError("wrong P-1 bounds")
    if receipt.get("program_exit_status") != 0:
        raise ValueError("P-1 did not exit successfully")
    classification = receipt.get("classification")
    if classification == "completed_no_factor_report":
        if receipt.get("factor") is not None:
            raise ValueError("no-factor receipt unexpectedly contains a factor")
        return "KEEP_PRP_RUNNING_AFTER_NO_FACTOR"
    if classification == "verified_factor":
        if not isinstance(receipt.get("factor"), str):
            raise ValueError("verified-factor receipt lacks factor")
        return "STOP_PRP_AFTER_VERIFIED_FACTOR"
    raise ValueError(f"inadmissible P-1 classification: {classification!r}")


def vm102_snapshot() -> str:
    command = (
        f"date -u; systemctl show {PRP_SERVICE} -p ActiveState -p SubState "
        "-p UnitFileState -p NRestarts -p ExecStart --no-pager; "
        "nvidia-smi --query-gpu=uuid,name,utilization.gpu,memory.used,temperature.gpu "
        "--format=csv,noheader; "
        f"sha256sum {PRP_RUN}/prpll {PRP_RUN}/run.sh; "
        f"tail -n 20 {PRP_RUN}/work/gpuowl-0.log; "
        f"find {PRP_RUN}/work/{EXPONENT} -maxdepth 1 -type f -name '*.prp' "
        "-printf '%s %f\\n' | sort"
    )
    return ssh(VM102, [command]).stdout


def write_json_atomic(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-deliverables", action="store_true")
    args = parser.parse_args()
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / ".guard.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("terminal P-1 guard already active")
            return 0
        decision_path = LOCAL / "guard-decision.json"
        if decision_path.is_file():
            document = json.loads(decision_path.read_text())
            if document.get("result") != "PASS":
                raise RuntimeError("existing terminal guard decision is not PASS")
            if args.refresh_deliverables:
                subprocess.run(
                    ["python3", str(ROOT / "refresh_deliverables.py")], check=True
                )
            print(f"existing decision: {document['decision']}")
            return 0

        marker = f"{P1_RUN}/completion-receipt.sha256"
        if not remote_file_exists(VM101, marker):
            print("waiting: M332228177 P-1 terminal receipt is not published")
            return 0

        with tempfile.TemporaryDirectory(prefix="M332228177-terminal-", dir=ROOT / "runs") as raw:
            tmp = Path(raw)
            hashes: dict[str, str] = {}
            for name in REMOTE_FILES:
                hashes[name] = stable_copy(VM101, f"{P1_RUN}/{name}", tmp / name)
            receipt = json.loads((tmp / "completion-receipt.json").read_text())
            decision = decision_for_receipt(receipt)
            if receipt.get("log_sha256") != hashes["run.log"]:
                raise RuntimeError("receipt does not bind the retained P-1 log")
            marker_hash = (tmp / "completion-receipt.sha256").read_text().split()[0]
            if marker_hash != hashes["completion-receipt.json"]:
                raise RuntimeError("completion marker does not bind receipt")
            provenance_check = ssh(
                VM101,
                [f"cd {P1_RUN} && sha256sum -c completion-provenance.sha256"],
            )
            (tmp / "remote-provenance-check.stdout").write_text(provenance_check.stdout)
            hashes["remote-provenance-check.stdout"] = digest(
                tmp / "remote-provenance-check.stdout"
            )

            before = vm102_snapshot()
            (tmp / "vm102-before.txt").write_text(before)
            if PRPLL_SHA not in before or "Tesla P40" not in before or "H200" in before:
                raise RuntimeError("VM102 exact P40/PRPLL binding failed")
            active_before = ssh(VM102, ["systemctl", "is-active", PRP_SERVICE], check=False)

            factor: str | None = None
            factor_sha: str | None = None
            if decision == "STOP_PRP_AFTER_VERIFIED_FACTOR":
                factor_sha = stable_copy(
                    VM101, f"{P1_RUN}/factor-certificate.json",
                    tmp / "factor-certificate.json",
                )
                certificate = json.loads((tmp / "factor-certificate.json").read_text())
                if certificate.get("schema") != "eff.mersenne-factor-certificate.v1":
                    raise RuntimeError("unexpected factor-certificate schema")
                if certificate.get("exponent") != EXPONENT:
                    raise RuntimeError("factor-certificate exponent mismatch")
                factor = str(certificate.get("factor"))
                if factor != receipt.get("factor"):
                    raise RuntimeError("receipt/certificate factor mismatch")
                if factor_sha != receipt.get("factor_certificate_sha256"):
                    raise RuntimeError("receipt/certificate hash mismatch")
                verify_factor(EXPONENT, int(factor))
                intent_text = (
                    f"intent_utc={utc_now()}\nexponent={EXPONENT}\nfactor={factor}\n"
                    f"factor_certificate_sha256={factor_sha}\n"
                )
                local_intent = tmp / "VERIFIED_FACTOR_STOP_INTENT.txt"
                remote_intent = f"{PRP_RUN}/VERIFIED_FACTOR_STOP_INTENT.txt"
                local_intent.write_text(intent_text)
                if remote_file_exists(VM102, remote_intent):
                    stable_copy(VM102, remote_intent, tmp / "remote-stop-intent.txt")
                    remote_text = (tmp / "remote-stop-intent.txt").read_text()
                    for required in (
                        f"exponent={EXPONENT}\n", f"factor={factor}\n",
                        f"factor_certificate_sha256={factor_sha}\n",
                    ):
                        if required not in remote_text:
                            raise RuntimeError("existing remote stop intent differs")
                else:
                    subprocess.run(
                        ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                         str(local_intent), f"{VM102}:{remote_intent}"],
                        check=True,
                    )
                    if remote_sha(VM102, remote_intent) != digest(local_intent):
                        raise RuntimeError("remote factor-stop intent copy mismatch")
                active_value = active_before.stdout.strip()
                recovered_stop = False
                if active_before.returncode == 0 and active_value == "active":
                    ssh(VM102, ["systemctl", "stop", PRP_SERVICE])
                elif active_value == "inactive" and remote_file_exists(VM102, remote_intent):
                    recovered_stop = True
                else:
                    raise RuntimeError(
                        "exact PRP service is neither active nor recoverably factor-stopped"
                    )
                ssh(VM102, ["systemctl", "disable", PRP_SERVICE])
                active_after = ssh(
                    VM102, ["systemctl", "is-active", PRP_SERVICE], check=False
                )
                if active_after.stdout.strip() != "inactive":
                    raise RuntimeError("PRP service did not become inactive")
                if ssh(VM102, ["pgrep", "-f", "(^|/)[p]rpll( |$)"], check=False).returncode == 0:
                    raise RuntimeError("PRPLL process survived verified-factor stop")
                marker_text = (
                    f"stopped_utc={utc_now()}\nexponent={EXPONENT}\nfactor={factor}\n"
                    f"factor_certificate_sha256={factor_sha}\n"
                )
                local_marker = tmp / "STOPPED_BY_VERIFIED_FACTOR.txt"
                local_marker.write_text(marker_text)
                subprocess.run(
                    ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                     str(local_marker), f"{VM102}:{PRP_RUN}/STOPPED_BY_VERIFIED_FACTOR.txt"],
                    check=True,
                )
                ledger_event = "result"
            else:
                if active_before.returncode != 0 or active_before.stdout.strip() != "active":
                    raise RuntimeError("no-factor result found but exact PRP is not active")
                ledger_event = "checkpoint"

            after = vm102_snapshot()
            (tmp / "vm102-after.txt").write_text(after)
            hashes["vm102-before.txt"] = digest(tmp / "vm102-before.txt")
            hashes["vm102-after.txt"] = digest(tmp / "vm102-after.txt")
            if decision == "STOP_PRP_AFTER_VERIFIED_FACTOR":
                if "ActiveState=inactive" not in after or "UnitFileState=disabled" not in after:
                    raise RuntimeError("post-factor VM102 state is not stopped and disabled")
            else:
                if "ActiveState=active" not in after:
                    raise RuntimeError("no-factor branch did not preserve active PRP")

            LOCAL.mkdir(parents=True, exist_ok=True)
            for path in tmp.iterdir():
                if path.is_file():
                    shutil.copy2(path, LOCAL / path.name)
            document: dict[str, object] = {
                "schema": "eff.M332228177-pminus1-prp-guard.v1",
                "captured_utc": utc_now(),
                "exponent": EXPONENT,
                "pminus1_bounds": {"b1": B1, "b2": B2},
                "classification": receipt["classification"],
                "decision": decision,
                "factor": factor,
                "factor_certificate_sha256": factor_sha,
                "recovered_after_interrupted_factor_stop": (
                    recovered_stop if decision == "STOP_PRP_AFTER_VERIFIED_FACTOR" else False
                ),
                "vm101": VM101_IP,
                "vm102": VM102_IP,
                "vm102_prp_service": PRP_SERVICE,
                "vm102_prpll_sha256": PRPLL_SHA,
                "expected_canonical_ledger_event": ledger_event,
                "canonical_ledger_writer": VM101_IP,
                "canonical_ledger_marker": (
                    "/root/eff-prime/runs/M332228213-pminus1-queued/"
                    "predecessor-ledger-published.txt"
                ),
                "local_ledger_write_performed": False,
                "evidence_sha256": hashes,
                "result": "PASS",
                "scope": (
                    "Cross-host early-abort guard. A no-factor screen is not a "
                    "primality result; a verified factor proves only compositeness."
                ),
            }
            write_json_atomic(decision_path, document)

        if args.refresh_deliverables:
            subprocess.run(["python3", str(ROOT / "refresh_deliverables.py")], check=True)
        print(f"PASS {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
