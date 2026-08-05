#!/bin/bash
# Checkpoint-safe PRPLL launcher for the independently reserved M332228177.

set -u

mode="${1:-run}"
if [ "$mode" != "run" ] && [ "$mode" != "--preflight-only" ]; then
    echo "usage: $0 [--preflight-only]" >&2
    exit 64
fi

expected_directory="/root/eff-prime/runs/M332228177-prp-20260805T0450Z"
expected_exponent=332228177
expected_gpu_uuid="GPU-a5c50372-9b4f-1496-eebf-f7220cd342fd"
expected_binary_sha256="04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
expected_reservation_sha256="084f19c8efc09a3a04c08efc26a1bcaf6e294351240e532ddfce9a773c0c0f6e"
expected_extension_sha256="715c5bb3175eb85ead1e4caef9fe664ab374556cd2d13ee894e67dfcb7280df8"
minimum_initial_free_bytes=100000000000

fail() {
    echo "refusing launch: $*" >&2
    exit 64
}

[ "$PWD" = "$expected_directory" ] || fail "unexpected working directory: $PWD"

actual_gpu_uuid="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)"
[ "$actual_gpu_uuid" = "$expected_gpu_uuid" ] || \
    fail "unexpected GPU UUID: $actual_gpu_uuid"

[ "$(sha256sum prpll | awk '{print $1}')" = "$expected_binary_sha256" ] || \
    fail "PRPLL binary hash mismatch"
[ "$(sha256sum reservation/M332228177.json | awk '{print $1}')" = \
    "$expected_reservation_sha256" ] || fail "original reservation hash mismatch"
[ "$(sha256sum reservation/M332228177-extension-20260805.json | awk '{print $1}')" = \
    "$expected_extension_sha256" ] || fail "reservation extension hash mismatch"

ssh-keygen -Y verify -f reservation/allowed_signers -I nadermx \
    -n eff-prime-reservation -s reservation/M332228177.json.sig \
    < reservation/M332228177.json >/dev/null || fail "original signature invalid"
ssh-keygen -Y verify -f reservation/allowed_signers -I nadermx \
    -n eff-prime-reservation-extension \
    -s reservation/M332228177-extension-20260805.json.sig \
    < reservation/M332228177-extension-20260805.json >/dev/null || \
    fail "extension signature invalid"

python3 - <<'PY' || fail "reservation scope or expiry mismatch"
import json
from datetime import datetime, timezone

original = json.load(open("reservation/M332228177.json", encoding="utf-8"))
extension = json.load(
    open("reservation/M332228177-extension-20260805.json", encoding="utf-8")
)
assert original["candidate"]["exponent"] == 332228177
assert original["candidate"]["exact_integer"] == "2^332228177-1"
assert extension["candidate"]["exponent"] == 332228177
assert extension["scope"]["exact_exponents_only"] == [332228177]
expiry = datetime.strptime(extension["new_expires_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
    tzinfo=timezone.utc
)
assert datetime.now(timezone.utc) < expiry
PY

mkdir -p work

if python3 verify_prpll_result.py work/results-0.txt \
    --exponent "$expected_exponent" --worktype PRP \
    > validated-result.json 2>/dev/null; then
    echo "validated terminal PRP result already exists; refusing duplicate work"
    exit 0
fi

if [ "$mode" = "--preflight-only" ]; then
    available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n 1 | tr -d ' ')"
    [ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || \
        fail "only $available_bytes bytes free; initial gate is $minimum_initial_free_bytes"
    echo "PASS: exact candidate, GPU, binary, signatures, expiry, and disk gate verified"
    exit 0
fi

if [ ! -f started_utc.txt ]; then
    available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n 1 | tr -d ' ')"
    [ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || \
        fail "only $available_bytes bytes free; initial gate is $minimum_initial_free_bytes"
    date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
fi

date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_started_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> before_gpu.csv
df -B1 "$expected_directory" >> disk_before.txt
sha256sum prpll run.sh verify_prpll_result.py reservation/* > input_provenance.sha256

set +e
/usr/bin/time -v ./prpll -dir work -device 0 -use NO_ASM \
    -prp "$expected_exponent" -noclean >> prpll.stdout 2>> prpll.time
run_status=$?
set -e

printf '%s\n' "$run_status" >> attempt_exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_ended_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> after_gpu.csv
df -B1 "$expected_directory" >> disk_after.txt

if [ "$run_status" -ne 0 ]; then
    exit "$run_status"
fi

if ! python3 verify_prpll_result.py work/results-0.txt \
    --exponent "$expected_exponent" --worktype PRP > validated-result.json; then
    echo "PRPLL exited zero without a complete exact-candidate result" >&2
    exit 75
fi

date -u +%Y-%m-%dT%H:%M:%SZ > completed_utc.txt
exit 0
