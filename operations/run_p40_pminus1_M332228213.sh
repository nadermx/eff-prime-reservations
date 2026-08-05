#!/bin/bash
# Exact one-shot launcher for the signed, queued M332228213 P-1 pass.

set -u

mode="${1:-run}"
if [ "$mode" != "run" ] && [ "$mode" != "--preflight-only" ]; then
    echo "usage: $0 [--preflight-only]" >&2
    exit 64
fi

expected_directory="/root/eff-prime/runs/M332228213-pminus1-queued"
expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
expected_binary_sha256="fb23ce4e30aff26f495edb3ccf45a6c847f42e9a1d0889c3f739c36cca2b4ff7"
expected_work_sha256="bfa33b45092dd792806f0a150a67a50d870657e1c4a153b00bb36b0abc9b7c0c"
expected_reservation_sha256="ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12"
authority="https://github.com/nadermx/eff-prime-reservations/commit/83b3472f12e7d571a6aa43bc478154e42b604289"

fail() {
    echo "refusing M332228213 P-1 launch: $*" >&2
    exit 64
}

[ "$PWD" = "$expected_directory" ] || fail "unexpected directory: $PWD"
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)" = \
    "$expected_gpu_uuid" ] || fail "unexpected GPU UUID"
[ "$(sha256sum CUDAPm1-system-gmp | awk '{print $1}')" = \
    "$expected_binary_sha256" ] || fail "binary hash mismatch"
[ "$(sha256sum worktodo.original.txt | awk '{print $1}')" = \
    "$expected_work_sha256" ] || fail "work hash mismatch"
cmp -s worktodo.original.txt worktodo.txt || fail "worktodo mismatch"
[ "$(sha256sum reservation/M332228213.json | awk '{print $1}')" = \
    "$expected_reservation_sha256" ] || fail "reservation hash mismatch"
ssh-keygen -Y verify -f reservation/allowed_signers -I nadermx \
    -n eff-prime-reservation -s reservation/M332228213.json.sig \
    < reservation/M332228213.json >/dev/null || fail "reservation signature invalid"

python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl >/dev/null || \
    fail "candidate ledger invalid"
python3 - "$authority" <<'PY' || fail "candidate authority gate"
import hashlib
import json
import sys
from datetime import datetime, timezone

authority = sys.argv[1]
reservation = json.load(open("reservation/M332228213.json", encoding="utf-8"))
preflight = json.load(open("preflight/preflight.json", encoding="utf-8"))
receipt = json.load(open("predecessor/completion-receipt.json", encoding="utf-8"))
assert reservation["candidate"]["exponent"] == 332228213
assert reservation["reservation_scope"]["exact_exponents_only"] == [332228213]
expiry = datetime.strptime(reservation["expires_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
assert datetime.now(timezone.utc) < expiry
assert preflight["exponent"] == 332228213
assert preflight["eligible_for_manual_reservation_review"] is True
assert preflight["assignment_record_present"] is False
assert preflight["published_status"] == "untested_no_known_factor"
fetched = datetime.strptime(preflight["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
age = (datetime.now(timezone.utc) - fetched).total_seconds()
assert 0 <= age <= 900
for field, path in (
    ("detailed_sha256", "preflight/primeNet-detailed.html"),
    ("factoring_sha256", "preflight/primeNet-factoring.json"),
):
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == preflight["official_sources"][field]

assert receipt["exponent"] == 332228177
assert receipt["classification"] in {"completed_no_factor_report", "verified_factor"}
if receipt["classification"] == "completed_no_factor_report":
    assert receipt["program_exit_status"] == 0
else:
    cert = json.load(open("predecessor/factor-certificate.json", encoding="utf-8"))
    factor = int(cert["factor"])
    assert cert["exponent"] == 332228177
    assert pow(2, 332228177, factor) == 1

records = [json.loads(line) for line in open("ledger/mersenne_candidates.jsonl", encoding="utf-8")]
history = [item for item in records if item.get("exponent") == 332228213]
assert [item["event"] for item in history[-3:]] == ["reservation", "status_snapshot", "work_started"]
assert history[-3]["authority_reference"] == authority
assert history[-1]["authority_reference"] == authority
assert history[-1]["evidence_sha256"] == history[-2]["evidence_sha256"]
actual_preflight = hashlib.sha256(open("preflight/preflight.json", "rb").read()).hexdigest()
assert history[-1]["evidence_sha256"] == actual_preflight
PY

if pgrep -f '[C]UDAPm1-system-gmp' >/dev/null; then
    fail "another CUDAPm1 process is active"
fi
if [ -e completion-receipt.json ] || [ -e exit_status.txt ]; then
    fail "result or attempt status already exists"
fi

if [ "$mode" = "--preflight-only" ]; then
    echo "PASS: candidate, reservation, ledger, predecessor, GPU, binary, and fresh-status gates"
    exit 0
fi

date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader > before_gpu.csv
sha256sum CUDAPm1-system-gmp CUDAPm1.ini worktodo.original.txt \
    TeslaP40_threads.txt run.sh reservation/* preflight/* predecessor/completion-receipt.json \
    ledger/mersenne_candidates.jsonl > input_provenance.sha256

runtime_library_path="/root/eff-prime/cudapm1/runtime12/nvidia/cufft/lib:/root/eff-prime/cudapm1/runtime12/nvidia/cuda_runtime/lib"
set +e
/usr/bin/time -v env CUDAPM1_ONE_SHOT=1 LD_LIBRARY_PATH="$runtime_library_path" \
    ./CUDAPm1-system-gmp -d 0 -i CUDAPm1.ini -f 19208K -nrp2 120 worktodo.txt \
    > run.log 2> run.time
run_status=$?
set -e
printf '%s\n' "$run_status" > exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ > ended_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader > after_gpu.csv
exit "$run_status"
