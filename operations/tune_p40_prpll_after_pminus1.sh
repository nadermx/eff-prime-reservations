#!/bin/bash
# Post-P-1 Tesla P40 PRPLL tuner.  This script cannot touch the live PRP lane.

set -u

expected_directory="/root/eff-prime/prpll-p40-tuning-20260805"
expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
expected_binary_sha256="04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
known_exponent=332192831
expected_residue="bff6cc96e2010c5c"
minimum_free_bytes=90000000000
mode="${1:-run}"

fail() {
    echo "refusing P40 tune: $*" >&2
    exit 64
}

if [ "$mode" != "run" ] && [ "$mode" != "--preflight-only" ]; then
    fail "usage: $0 [--preflight-only]"
fi
[ "$PWD" = "$expected_directory" ] || fail "unexpected working directory: $PWD"

if systemctl is-active --quiet eff-pm1-m332228177.service; then
    fail "candidate P-1 service is still active"
fi
if pgrep -f '[C]UDAPm1-system-gmp' >/dev/null; then
    fail "CUDAPm1 process is still active"
fi

actual_gpu_uuid="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)"
[ "$actual_gpu_uuid" = "$expected_gpu_uuid" ] || \
    fail "unexpected GPU UUID: $actual_gpu_uuid"
[ "$(sha256sum prpll | awk '{print $1}')" = "$expected_binary_sha256" ] || \
    fail "PRPLL binary hash mismatch"

available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n 1 | tr -d ' ')"
[ "$available_bytes" -ge "$minimum_free_bytes" ] || \
    fail "only $available_bytes bytes free; gate is $minimum_free_bytes"

python3 - <<'PY' || fail "VM102 health receipt is absent, stale, or invalid"
import json
from datetime import datetime, timezone

receipt = json.load(open("vm102-active-receipt.json", encoding="utf-8"))
assert receipt["schema"] == "eff-vm102-prp-health-v1"
assert receipt["service"] == "eff-prp-m332228177.service"
assert receipt["service_state"] == "active"
assert receipt["gpu_uuid"] == "GPU-a5c50372-9b4f-1496-eebf-f7220cd342fd"
assert receipt["restart_count"] >= 0
fetched = datetime.strptime(receipt["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
    tzinfo=timezone.utc
)
age = (datetime.now(timezone.utc) - fetched).total_seconds()
assert -30 <= age <= 600
PY

if [ "$mode" = "--preflight-only" ]; then
    echo "PASS: P-1 released, expected P40/binary/disk present, VM102 PRP active"
    exit 0
fi

[ ! -e tune ] || fail "tune output already exists"
[ ! -e baseline-10000 ] || fail "baseline output already exists"
[ ! -e tuned-10000 ] || fail "tuned output already exists"
mkdir tune baseline-10000 tuned-10000

date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader > before_gpu.csv
sha256sum prpll run.sh > input_provenance.sha256

set +e
/usr/bin/time -v ./prpll -dir tune -device 0 -use NO_ASM -cache \
    -tune noconfig,inplace,ntt,nofp32,minexp=300000000,maxexp=360000000,quick=5 \
    > tune.stdout 2> tune.time
tune_status=$?
set -e
printf '%s\n' "$tune_status" > tune_exit_status.txt
[ "$tune_status" -eq 0 ] || exit "$tune_status"
[ -s tune/tune.txt ] || fail "tuner did not produce tune/tune.txt"

cp tune/tune.txt tuned-10000/tune.txt
if [ -s tune/config.txt ]; then
    cp tune/config.txt tuned-10000/config.txt
fi

set +e
/usr/bin/time -v ./prpll -dir baseline-10000 -device 0 -use NO_ASM \
    -prp "$known_exponent" -iters 10000 -noclean \
    > baseline.stdout 2> baseline.time
baseline_status=$?
/usr/bin/time -v ./prpll -dir tuned-10000 -device 0 -use NO_ASM \
    -prp "$known_exponent" -iters 10000 -noclean \
    > tuned.stdout 2> tuned.time
tuned_status=$?
set -e
printf '%s\n' "$baseline_status" > baseline_exit_status.txt
printf '%s\n' "$tuned_status" > tuned_exit_status.txt
[ "$baseline_status" -eq 0 ] || exit "$baseline_status"
[ "$tuned_status" -eq 0 ] || exit "$tuned_status"

python3 - "$expected_residue" <<'PY'
import json
import re
import sys
from pathlib import Path

expected = sys.argv[1]
pattern = re.compile(r"332192831 OK\s+10000 ([0-9a-f]{16}) (\d+)")

def final_sample(path: str) -> tuple[str, int]:
    matches = pattern.findall(Path(path).read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise SystemExit(f"expected one final sample in {path}; found {len(matches)}")
    return matches[0][0], int(matches[0][1])

baseline_residue, baseline_us = final_sample("baseline-10000/gpuowl-0.log")
tuned_residue, tuned_us = final_sample("tuned-10000/gpuowl-0.log")
if baseline_residue != expected or tuned_residue != expected:
    raise SystemExit(
        f"residue mismatch: baseline={baseline_residue} tuned={tuned_residue}"
    )
ratio = tuned_us / baseline_us
decision = "PROMOTION_REVIEW" if ratio <= 0.97 else "DO_NOT_PROMOTE"
result = {
    "schema": "eff-prpll-p40-tuning-decision-v1",
    "known_composite_exponent": 332192831,
    "expected_and_observed_residue64": expected,
    "baseline_microseconds_per_iteration": baseline_us,
    "tuned_microseconds_per_iteration": tuned_us,
    "tuned_to_baseline_ratio": ratio,
    "minimum_improvement_for_review": 0.03,
    "decision": decision,
    "automatic_live_prp_change_allowed": False,
}
Path("decision.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(result, sort_keys=True))
PY

date -u +%Y-%m-%dT%H:%M:%SZ > ended_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader > after_gpu.csv
output_files=(
    tune/tune.txt baseline-10000/gpuowl-0.log
    tuned-10000/gpuowl-0.log decision.json
)
if [ -s tune/config.txt ]; then
    output_files+=(tune/config.txt)
fi
sha256sum "${output_files[@]}" > output_provenance.sha256

echo "Tune experiment complete; decision.json is advisory and cannot change VM102."
