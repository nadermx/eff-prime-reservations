#!/bin/bash
# Distinct CPU/Mlucas LL confirmation for a proof-verified M332228213 hit.

set -euo pipefail

mode="${1:-run}"
if [ "$mode" != run ] && [ "$mode" != --preflight-only ]; then
    echo "usage: $0 [--preflight-only]" >&2
    exit 64
fi

expected_directory="/home/john/eff/runs/M332228213-mlucas-queued"
expected_exponent=332228213
expected_binary_sha256="b9d89a8e1a2c2c558c86fad6ead3fd311fd93e9eb67bda1bdf8f9f98c81f3d56"
expected_source_sha256="7d077166c5d34869e7a08b78cb838317a2ba1a51277fb17ce79c964d987efacb"
expected_config_sha256="b7eba0cdaa68484642fc4793392a5fd15135d3994b26cf462d6600e09dbdfeca"
expected_result_verifier_sha256="d95f66a12fe0f39d0609860a7fbc2a996d2fc428dd415efe57d3adb1d4909c0e"
minimum_initial_free_bytes=5000000000

fail() { echo "refusing M332228213 Mlucas confirmation launch: $*" >&2; exit 64; }

[ "$PWD" = "$expected_directory" ] || fail "unexpected working directory: $PWD"
[ "$(sha256sum Mlucas-main-4a21413-avx2-safe | awk '{print $1}')" = "$expected_binary_sha256" ] || fail "Mlucas binary mismatch"
[ "$(sha256sum Mlucas-main-4a21413-source.tar.gz | awk '{print $1}')" = "$expected_source_sha256" ] || fail "Mlucas source archive mismatch"
[ "$(sha256sum mlucas.cfg | awk '{print $1}')" = "$expected_config_sha256" ] || fail "validated M332228213 radix configuration mismatch"
[ "$(sha256sum verify_mlucas_result.py | awk '{print $1}')" = "$expected_result_verifier_sha256" ] || fail "Mlucas result verifier mismatch"
[ "$(tr -d '\r\n' < worktodo.original.txt)" = "Test=$expected_exponent" ] || fail "worktodo exponent mismatch"
[ -f predecessor/MANIFEST.sha256 ] || fail "predecessor manifest absent"
(cd predecessor && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "predecessor manifest mismatch"

python3 - <<'PY' || fail "probable-prime transition gate failed"
import json
transition = json.load(open("predecessor/transition-receipt.json", encoding="utf-8"))
verification = json.load(open("predecessor/proof-verification-receipt.json", encoding="utf-8"))
result = json.load(open("predecessor/validated-prp-result.json", encoding="utf-8"))
assert transition["exponent"] == 332228213
assert transition["classification"] == "probable_prime_trigger"
assert transition["deterministic_lucas_lehmer_required"] is True
assert verification["result"] == "PASS"
assert verification["proof_sha256"] == transition["proof"]["sha256"]
assert result["exponent"] == 332228213
assert result["worktype"] == "PRP-3"
assert result["status"] == "P"
assert result["errors"] == {"gerbicz": 0}
PY

if python3 verify_mlucas_result.py p332228213.stat \
    --exponent "$expected_exponent" > validated-mlucas-result.json 2>/dev/null; then
    echo "validated terminal M332228213 Mlucas result already exists; refusing duplicate work"
    exit 0
fi

available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n1 | tr -d ' ')"
[ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || fail "insufficient disk: $available_bytes"
if pgrep -f '[M]lucas.*332228213|[M]lucas-main-4a21413-avx2-safe' >/dev/null; then fail "Mlucas target process already active"; fi

if [ "$mode" = --preflight-only ]; then
    echo "PASS: proof-verified M332228213 trigger, distinct CPU binary/source, radix, and disk gates"
    exit 0
fi

if [ ! -f started_utc.txt ]; then
    date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
    cp worktodo.original.txt worktodo.txt
    uname -a > hardware-and-os.txt
    lscpu >> hardware-and-os.txt
    free -b >> hardware-and-os.txt
    sha256sum Mlucas-main-4a21413-avx2-safe Mlucas-main-4a21413-source.tar.gz \
        mlucas.cfg worktodo.original.txt run.sh verify_mlucas_result.py \
        predecessor/* > input_provenance.sha256
fi

export CUDA_VISIBLE_DEVICES=""
date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_started_utc.txt
set +e
/usr/bin/time -v ./Mlucas-main-4a21413-avx2-safe -nthread 12 \
    >> mlucas.stdout 2>> mlucas.time
run_status=$?
set -e
printf '%s\n' "$run_status" >> attempt_exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_ended_utc.txt
[ "$run_status" -eq 0 ] || exit "$run_status"

python3 verify_mlucas_result.py p332228213.stat \
    --exponent "$expected_exponent" > validated-mlucas-result.json || {
        echo "Mlucas exited zero without an admissible exact M332228213 LL result" >&2
        exit 75
    }

python3 - <<'PY'
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

result = json.load(open("validated-mlucas-result.json", encoding="utf-8"))
receipt = {
    "schema": "eff.mlucas-independent-lucas-lehmer-result.v1",
    "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "exponent": 332228213,
    "classification": "deterministic_prime" if result["status"] == "P" else "deterministic_composite",
    "status": result["status"],
    "terminal_res64": result["res64"].upper(),
    "zero_residue_required_and_observed": result["status"] == "P" and result["res64"].upper() == "0000000000000000",
    "validated_result_sha256": digest("validated-mlucas-result.json"),
    "stat_file_sha256": digest("p332228213.stat"),
    "mlucas_stdout_sha256": digest("mlucas.stdout"),
    "mlucas_time_sha256": digest("mlucas.time"),
    "distinct_software": "Mlucas 21.0.2 commit 4a21413 on CPU",
    "h200_used": False,
    "scope": "Independent deterministic M332228213 Lucas-Lehmer confirmation; publication and EFF claim remain separate gates.",
}
Path("completion-receipt.json.tmp").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path("completion-receipt.json.tmp").replace("completion-receipt.json")
PY
sha256sum completion-receipt.json validated-mlucas-result.json p332228213.stat mlucas.stdout mlucas.time > completion-provenance.sha256
date -u +%Y-%m-%dT%H:%M:%SZ > completion-published.txt.tmp
mv completion-published.txt.tmp completion-published.txt
