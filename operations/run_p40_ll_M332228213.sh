#!/bin/bash
# Deterministic Lucas--Lehmer run for M332228213 after a proof-verified PRP hit.

set -euo pipefail

mode="${1:-run}"
if [ "$mode" != run ] && [ "$mode" != --preflight-only ]; then
    echo "usage: $0 [--preflight-only]" >&2
    exit 64
fi

expected_directory="/root/eff-prime/runs/M332228213-ll-queued"
expected_exponent=332228213
expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
expected_binary_sha256="04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
expected_verifier_sha256="7cb64288e184472df792af28db562415785d42fd43265338965a3349fb4484ec"
expected_reservation_sha256="ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12"
minimum_initial_free_bytes=10000000000

fail() { echo "refusing M332228213 Lucas-Lehmer launch: $*" >&2; exit 64; }

[ "$PWD" = "$expected_directory" ] || fail "unexpected working directory: $PWD"
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n1)" = "$expected_gpu_uuid" ] || fail "GPU UUID mismatch"
[ "$(sha256sum prpll | awk '{print $1}')" = "$expected_binary_sha256" ] || fail "PRPLL binary hash mismatch"
[ "$(sha256sum verify_prpll_result.py | awk '{print $1}')" = "$expected_verifier_sha256" ] || fail "result verifier hash mismatch"
[ "$(sha256sum reservation/M332228213.json | awk '{print $1}')" = "$expected_reservation_sha256" ] || fail "reservation hash mismatch"
ssh-keygen -Y verify -f reservation/allowed_signers -I nadermx \
    -n eff-prime-reservation -s reservation/M332228213.json.sig \
    < reservation/M332228213.json >/dev/null || fail "reservation signature invalid"

[ -f predecessor/MANIFEST.sha256 ] || fail "predecessor manifest absent"
(cd predecessor && sha256sum -c MANIFEST.sha256 >/dev/null) || fail "predecessor manifest mismatch"
python3 - <<'PY' || fail "probable-prime/proof-verification gate failed"
import json
transition = json.load(open("predecessor/transition-receipt.json", encoding="utf-8"))
verification = json.load(open("predecessor/proof-verification-receipt.json", encoding="utf-8"))
result = json.load(open("predecessor/validated-prp-result.json", encoding="utf-8"))
assert transition["schema"] == "eff.prpll-prp-to-ll-transition.v1"
assert transition["exponent"] == 332228213
assert transition["classification"] == "probable_prime_trigger"
assert transition["deterministic_lucas_lehmer_required"] is True
assert verification["schema"] == "eff.prpll-proof-execution-verification.v1"
assert verification["exponent"] == 332228213
assert verification["result"] == "PASS"
assert verification["proof_sha256"] == transition["proof"]["sha256"]
assert result["exponent"] == 332228213
assert result["worktype"] == "PRP-3"
assert result["status"] == "P"
assert result["errors"] == {"gerbicz": 0}
PY

if python3 verify_prpll_result.py work/results-0.txt \
    --exponent "$expected_exponent" --worktype LL \
    > validated-ll-result.json 2>/dev/null; then
    echo "validated terminal M332228213 Lucas-Lehmer result already exists; refusing duplicate work"
    exit 0
fi

if [ "$mode" = --preflight-only ]; then
    available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n1 | tr -d ' ')"
    [ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || fail "insufficient disk: $available_bytes"
    if pgrep -f '(^|/)[p]rpll( |$)' >/dev/null; then fail "another PRPLL process is active"; fi
    echo "PASS: proof-verified M332228213 PRP trigger, P40, binary, signature, and disk gates"
    exit 0
fi

if pgrep -f '(^|/)[p]rpll( |$)' >/dev/null; then fail "another PRPLL process is active"; fi
available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n1 | tr -d ' ')"
[ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || fail "insufficient disk: $available_bytes"

mkdir -p work
date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader > before_gpu.csv
sha256sum prpll run.sh verify_prpll_result.py reservation/* predecessor/* > input_provenance.sha256

set +e
/usr/bin/time -v ./prpll -dir work -device 0 -use NO_ASM \
    -ll "$expected_exponent" -noclean > prpll.stdout 2> prpll.time
run_status=$?
set -e
printf '%s\n' "$run_status" > exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ > ended_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader > after_gpu.csv
[ "$run_status" -eq 0 ] || exit "$run_status"

python3 verify_prpll_result.py work/results-0.txt \
    --exponent "$expected_exponent" --worktype LL > validated-ll-result.json || {
        echo "PRPLL exited zero without an admissible exact M332228213 LL result" >&2
        exit 75
    }

python3 - <<'PY'
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

result = json.load(open("validated-ll-result.json", encoding="utf-8"))
classification = "deterministic_prime" if result["status"] == "P" else "deterministic_composite"
receipt = {
    "schema": "eff.prpll-lucas-lehmer-result.v1",
    "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "exponent": 332228213,
    "classification": classification,
    "status": result["status"],
    "terminal_res64": result["res64"].lower(),
    "zero_residue_required_and_observed": result["status"] == "P" and result["res64"] == "0000000000000000",
    "validated_result_sha256": digest("validated-ll-result.json"),
    "raw_results_sha256": digest("work/results-0.txt"),
    "prpll_stdout_sha256": digest("prpll.stdout"),
    "prpll_time_sha256": digest("prpll.time"),
    "independent_mlucas_confirmation_required": result["status"] == "P",
    "scope": "Deterministic M332228213 Lucas-Lehmer computation; independent Mlucas confirmation and publication remain separate gates.",
}
Path("completion-receipt.json.tmp").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
Path("completion-receipt.json.tmp").replace("completion-receipt.json")
PY
sha256sum completion-receipt.json validated-ll-result.json work/results-0.txt prpll.stdout prpll.time > completion-provenance.sha256
date -u +%Y-%m-%dT%H:%M:%SZ > completion-published.txt.tmp
mv completion-published.txt.tmp completion-published.txt
