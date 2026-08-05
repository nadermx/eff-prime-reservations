#!/bin/bash
# Checkpoint-safe PRPLL launcher for independently reserved M332228213.

set -u
mode="${1:-run}"
if [ "$mode" != "run" ] && [ "$mode" != "--preflight-only" ]; then
    echo "usage: $0 [--preflight-only]" >&2
    exit 64
fi

expected_directory="/root/eff-prime/runs/M332228213-prp-queued"
expected_exponent=332228213
expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
expected_binary_sha256="04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
expected_reservation_sha256="ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12"
authority="https://github.com/nadermx/eff-prime-reservations/commit/83b3472f12e7d571a6aa43bc478154e42b604289"
minimum_initial_free_bytes=100000000000

fail() { echo "refusing M332228213 PRP launch: $*" >&2; exit 64; }
[ "$PWD" = "$expected_directory" ] || fail "unexpected directory"
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)" = \
  "$expected_gpu_uuid" ] || fail "unexpected GPU UUID"
[ "$(sha256sum prpll | awk '{print $1}')" = "$expected_binary_sha256" ] || \
  fail "PRPLL binary hash mismatch"
[ "$(sha256sum reservation/M332228213.json | awk '{print $1}')" = \
  "$expected_reservation_sha256" ] || fail "reservation hash mismatch"
ssh-keygen -Y verify -f reservation/allowed_signers -I nadermx \
    -n eff-prime-reservation -s reservation/M332228213.json.sig \
    < reservation/M332228213.json >/dev/null || fail "reservation signature invalid"

python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl >/dev/null || \
    fail "candidate ledger invalid"
python3 - "$authority" <<'PY' || fail "candidate/P-1/status/ledger gate"
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
assert receipt["exponent"] == 332228213
assert receipt["b1"] == 1495000 and receipt["b2"] == 32142500
assert receipt["program_exit_status"] == 0
assert receipt["classification"] == "completed_no_factor_report"
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
    actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert actual == preflight["official_sources"][field]
records = [json.loads(line) for line in open("ledger/mersenne_candidates.jsonl", encoding="utf-8")]
history = [item for item in records if item.get("exponent") == 332228213]
assert [item["event"] for item in history[-3:]] == ["checkpoint", "status_snapshot", "lane_started"]
assert any(item["event"] == "work_started" for item in history[:-3])
assert history[-1]["authority_reference"] == authority
assert history[-1]["evidence_sha256"] == history[-2]["evidence_sha256"]
actual_preflight = hashlib.sha256(open("preflight/preflight.json", "rb").read()).hexdigest()
assert history[-1]["evidence_sha256"] == actual_preflight
PY

pgrep -f '[C]UDAPm1-system-gmp' >/dev/null && fail "CUDAPm1 is active"
if pgrep -f '(^|/)[p]rpll( |$)' >/dev/null; then fail "another PRPLL process is active"; fi
mkdir -p work
if python3 verify_prpll_result.py work/results-0.txt --exponent "$expected_exponent" \
    --worktype PRP > validated-result.json 2>/dev/null; then
    echo "validated terminal PRP result already exists; refusing duplicate work"
    exit 0
fi

available_bytes="$(df -B1 --output=avail "$expected_directory" | tail -n 1 | tr -d ' ')"
if [ ! -f started_utc.txt ]; then
    [ "$available_bytes" -ge "$minimum_initial_free_bytes" ] || \
        fail "only $available_bytes bytes free; need $minimum_initial_free_bytes"
fi
if [ "$mode" = "--preflight-only" ]; then
    echo "PASS: exact candidate, no-factor P-1, status, ledger, GPU, binary, signature, and disk gates"
    exit 0
fi

[ -f started_utc.txt ] || date -u +%Y-%m-%dT%H:%M:%SZ > started_utc.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_started_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> before_gpu.csv
df -B1 "$expected_directory" >> disk_before.txt
sha256sum prpll run.sh verify_prpll_result.py reservation/* preflight/* \
    predecessor/completion-receipt.json ledger/mersenne_candidates.jsonl \
    > input_provenance.sha256

set +e
/usr/bin/time -v ./prpll -dir work -device 0 -use NO_ASM \
    -prp "$expected_exponent" -noclean >> prpll.stdout 2>> prpll.time
status=$?
set -e
printf '%s\n' "$status" >> attempt_exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> attempt_ended_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> after_gpu.csv
df -B1 "$expected_directory" >> disk_after.txt
[ "$status" -eq 0 ] || exit "$status"
python3 verify_prpll_result.py work/results-0.txt --exponent "$expected_exponent" \
    --worktype PRP > validated-result.json || {
        echo "PRPLL exited zero without an exact terminal result" >&2
        exit 75
    }
date -u +%Y-%m-%dT%H:%M:%SZ > completed_utc.txt
