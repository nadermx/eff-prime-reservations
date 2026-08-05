#!/bin/bash
# Failure/reboot recovery for the exact M332228213 P-1 pass.

set -u
expected_directory="/root/eff-prime/runs/M332228213-pminus1-queued"
fail() { echo "refusing M332228213 P-1 resume: $*" >&2; exit 64; }
[ "$PWD" = "$expected_directory" ] || fail "unexpected directory"
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)" = \
  "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2" ] || fail "unexpected GPU"
[ "$(sha256sum CUDAPm1-system-gmp | awk '{print $1}')" = \
  "fb23ce4e30aff26f495edb3ccf45a6c847f42e9a1d0889c3f739c36cca2b4ff7" ] || fail "binary hash"
[ "$(sha256sum worktodo.original.txt | awk '{print $1}')" = \
  "bfa33b45092dd792806f0a150a67a50d870657e1c4a153b00bb36b0abc9b7c0c" ] || fail "work hash"
cmp -s worktodo.original.txt worktodo.txt || fail "worktodo mismatch"
if [ -f exit_status.txt ] && [ "$(cat exit_status.txt)" = 0 ]; then
    echo "clean result already recorded"
    exit 0
fi
checkpoint="c332228213s1"
[ -f c332228213s2 ] && checkpoint="c332228213s2"
[ -f "$checkpoint" ] || fail "no stage checkpoint"
python3 /root/eff-prime/cudapm1/cudapm1_checkpoint_gcd.py --metadata-only \
    "$checkpoint" > resume-checkpoint-metadata.json
python3 - <<'PY' || fail "checkpoint metadata"
import json
x = json.load(open("resume-checkpoint-metadata.json", encoding="utf-8"))
assert x["exponent"] == 332228213 and x["b1"] == 1495000 and x["stage"] in (1, 2)
PY
date -u +%Y-%m-%dT%H:%M:%SZ >> resume_started_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> resume_before_gpu.csv
runtime_library_path="/root/eff-prime/cudapm1/runtime12/nvidia/cufft/lib:/root/eff-prime/cudapm1/runtime12/nvidia/cuda_runtime/lib"
set +e
/usr/bin/time -v env CUDAPM1_ONE_SHOT=1 LD_LIBRARY_PATH="$runtime_library_path" \
    ./CUDAPm1-system-gmp -d 0 -i CUDAPm1.ini -f 19208K -nrp2 120 worktodo.txt \
    >> run.log 2>> run.time
status=$?
set -e
printf '%s\n' "$status" > exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> resume_ended_utc.txt
nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> resume_after_gpu.csv
exit "$status"
