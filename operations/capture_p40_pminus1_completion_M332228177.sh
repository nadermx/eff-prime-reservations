#!/bin/bash
# One-shot completion receipt for the fixed VM101 M332228177 P-1 pass.

set -u

expected_directory="/root/eff-prime/runs/M332228177-pminus1-20260805T0412Z"
expected_binary_sha256="fb23ce4e30aff26f495edb3ccf45a6c847f42e9a1d0889c3f739c36cca2b4ff7"
expected_work_sha256="d32316c405e1f0d08ab700ccdd460eefe13e424625d4c9dff1bdaf6b50d6c109"

fail() {
    echo "refusing P-1 completion capture: $*" >&2
    exit 64
}

[ "$PWD" = "$expected_directory" ] || fail "unexpected directory: $PWD"
[ -f exit_status.txt ] || fail "exit status does not exist"
if [ -f completion-receipt.json ]; then
    echo "completion receipt already exists; refusing duplicate capture"
    exit 0
fi
if pgrep -f '[C]UDAPm1-system-gmp' >/dev/null; then
    fail "CUDAPm1 is still running"
fi
[ "$(sha256sum CUDAPm1-system-gmp | awk '{print $1}')" = \
    "$expected_binary_sha256" ] || fail "binary hash mismatch"
[ "$(sha256sum worktodo.original.txt | awk '{print $1}')" = \
    "$expected_work_sha256" ] || fail "work hash mismatch"

exit_status="$(cat exit_status.txt)"
case "$exit_status" in
    ''|*[!0-9]*) fail "non-numeric exit status: $exit_status" ;;
esac

python3 /root/eff-prime/cudapm1/classify_cudapm1_result.py run.log \
    --exponent 332228177 --b1 1495000 --b2 32142500 \
    --exit-status "$exit_status" --receipt completion-receipt.json \
    --factor-certificate factor-certificate.json \
    > completion-classifier.stdout

date -u +%Y-%m-%dT%H:%M:%SZ > completion-captured_utc.txt
completion_files=(
    completion-receipt.json completion-classifier.stdout exit_status.txt
    run.log run.time ended_utc.txt after_gpu.csv
)
if [ -f factor-certificate.json ]; then
    completion_files+=(factor-certificate.json)
fi
sha256sum "${completion_files[@]}" > completion-provenance.sha256
sha256sum completion-receipt.json > completion-receipt.sha256

echo "P-1 completion captured; no follow-on computation was started."
