#!/bin/bash
# Reboot/failure-only resume wrapper; the initial launch uses run.sh.
# Stage 2 is capped at nrp2=120 after the automatic nrp=138 layout consumed
# 24.16 GB and reproducibly faulted immediately after initialization.  The
# lower cap leaves about 4 GB of P40 VRAM headroom and does not change B1/B2.

set -u

expected_directory="/root/eff-prime/runs/M332228177-pminus1-20260805T0412Z"
if [ "$PWD" != "$expected_directory" ]; then
    echo "refusing unexpected working directory: $PWD" >&2
    exit 64
fi

expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
actual_gpu_uuid="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)"
if [ "$actual_gpu_uuid" != "$expected_gpu_uuid" ]; then
    echo "refusing unexpected GPU UUID: $actual_gpu_uuid" >&2
    exit 69
fi

if [ -f exit_status.txt ] && [ "$(cat exit_status.txt)" = "0" ]; then
    echo "clean result already recorded; refusing to repeat completed P-1 work" >&2
    exit 0
fi

if [ "$(sha256sum CUDAPm1-system-gmp | awk '{print $1}')" != \
     "fb23ce4e30aff26f495edb3ccf45a6c847f42e9a1d0889c3f739c36cca2b4ff7" ]; then
    echo "refusing binary hash mismatch" >&2
    exit 65
fi

if [ "$(sha256sum worktodo.original.txt | awk '{print $1}')" != \
     "d32316c405e1f0d08ab700ccdd460eefe13e424625d4c9dff1bdaf6b50d6c109" ]; then
    echo "refusing original work hash mismatch" >&2
    exit 66
fi

if ! cmp -s worktodo.original.txt worktodo.txt; then
    echo "refusing partial worktodo mismatch" >&2
    exit 67
fi

if [ ! -f c332228177s1 ] && [ ! -f c332228177s2 ]; then
    echo "refusing resume without a stage checkpoint" >&2
    exit 68
fi

checkpoint_file="c332228177s1"
if [ -f c332228177s2 ]; then
    checkpoint_file="c332228177s2"
fi
python3 /root/eff-prime/cudapm1/cudapm1_checkpoint_gcd.py \
    --metadata-only "$checkpoint_file" > resume-checkpoint-metadata.json
python3 -c 'import json; x=json.load(open("resume-checkpoint-metadata.json")); assert x["exponent"] == 332228177; assert x["b1"] == 1495000; assert x["stage"] in (1, 2)'

date -u +%Y-%m-%dT%H:%M:%SZ >> resume_started_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> resume_before_gpu.csv

runtime_library_path="/root/eff-prime/cudapm1/runtime12/nvidia/cufft/lib:/root/eff-prime/cudapm1/runtime12/nvidia/cuda_runtime/lib"

set +e
/usr/bin/time -v env \
    CUDAPM1_ONE_SHOT=1 \
    LD_LIBRARY_PATH="$runtime_library_path" \
    ./CUDAPm1-system-gmp -d 0 -i CUDAPm1.ini -f 19208K -nrp2 120 worktodo.txt \
    >> run.log 2>> run.time
resume_status=$?
set -e

printf '%s\n' "$resume_status" > exit_status.txt
date -u +%Y-%m-%dT%H:%M:%SZ >> resume_ended_utc.txt
nvidia-smi \
    --query-gpu=timestamp,name,uuid,driver_version,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu \
    --format=csv,noheader >> resume_after_gpu.csv

exit "$resume_status"
