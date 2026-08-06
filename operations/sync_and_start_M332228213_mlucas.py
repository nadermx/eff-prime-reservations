#!/usr/bin/env python3
"""Fetch a proof-verified M332228213 PRP hit and start distinct Mlucas LL."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTE = "root@38.86.78.5"
REMOTE_PRP = "/root/eff-prime/runs/M332228213-prp-queued"
REMOTE_PREDECESSOR = "/root/eff-prime/runs/M332228213-ll-queued/predecessor"
LOCAL = ROOT / "runs/M332228213-mlucas-queued"
SERVICE = "eff-mlucas-m332228213.service"
FILES = (
    "validated-prp-result.json",
    "transition-receipt.json",
    "proof-verification-receipt.json",
    "prp-proof.sha256",
    "MANIFEST.sha256",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def ssh(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE, command],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def main() -> int:
    if (LOCAL / "completion-published.txt").exists():
        print("complete: independent M332228213 Mlucas receipt already published")
        return 0
    marker = ssh(f"test -e {REMOTE_PRP}/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt")
    if marker.returncode != 0:
        print("waiting: proof-verified M332228213 probable-prime trigger is absent")
        return 0
    if (LOCAL / "started_utc.txt").exists():
        active = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", SERVICE],
            check=False,
        )
        if active.returncode != 0:
            subprocess.run(["systemctl", "--user", "start", SERVICE], check=True)
            print("resumed: distinct CPU/Mlucas M332228213 confirmation")
        else:
            print("active: distinct CPU/Mlucas M332228213 confirmation")
        return 0

    LOCAL.mkdir(parents=True, exist_ok=True)
    predecessor = LOCAL / "predecessor"
    if predecessor.exists():
        raise RuntimeError("predecessor directory exists without a local start marker")
    with tempfile.TemporaryDirectory(prefix="eff-M332228213-mlucas-trigger-", dir=ROOT / "runs") as raw:
        temporary = Path(raw)
        subprocess.run(
            ["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
             *[f"{REMOTE}:{REMOTE_PREDECESSOR}/{name}" for name in FILES], str(temporary)],
            check=True,
        )
        subprocess.run(
            ["sha256sum", "-c", "MANIFEST.sha256"], cwd=temporary,
            stdout=subprocess.DEVNULL, check=True,
        )
        transition = json.loads((temporary / "transition-receipt.json").read_text())
        verification = json.loads((temporary / "proof-verification-receipt.json").read_text())
        result = json.loads((temporary / "validated-prp-result.json").read_text())
        if transition["exponent"] != 332228213 or transition["classification"] != "probable_prime_trigger":
            raise RuntimeError("remote transition is not an exact M332228213 probable-prime trigger")
        if verification["result"] != "PASS" or verification["proof_sha256"] != transition["proof"]["sha256"]:
            raise RuntimeError("remote execution-proof verification is inadmissible")
        if result.get("exponent") != 332228213 or result.get("worktype") != "PRP-3" or result.get("status") != "P":
            raise RuntimeError("remote PRP result is not an exact M332228213 hit")
        if result.get("errors") != {"gerbicz": 0}:
            raise RuntimeError("remote PRP result reports errors")
        remote_hashes = ssh("sha256sum " + " ".join(f"{REMOTE_PREDECESSOR}/{name}" for name in FILES))
        if remote_hashes.returncode != 0:
            raise RuntimeError(remote_hashes.stderr)
        expected = {
            Path(line.split(None, 1)[1]).name: line.split(None, 1)[0]
            for line in remote_hashes.stdout.splitlines()
        }
        for name in FILES:
            if digest(temporary / name) != expected[name]:
                raise RuntimeError(f"remote/local M332228213 transfer mismatch: {name}")
        shutil.copytree(temporary, predecessor)

    subprocess.run(
        [str(LOCAL / "run.sh"), "--preflight-only"], cwd=LOCAL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    subprocess.run(["systemctl", "--user", "start", SERVICE], check=True)
    print("started: distinct CPU/Mlucas M332228213 Lucas-Lehmer confirmation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
