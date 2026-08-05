#!/bin/bash
# Classify the exact M332228213 P-1 terminal record; starts nothing else.

set -u
expected_directory="/root/eff-prime/runs/M332228213-pminus1-queued"
fail() { echo "refusing M332228213 completion capture: $*" >&2; exit 64; }
[ "$PWD" = "$expected_directory" ] || fail "unexpected directory"
[ -f exit_status.txt ] || fail "missing exit status"
[ ! -f completion-receipt.json ] || exit 0
pgrep -f '[C]UDAPm1-system-gmp' >/dev/null && fail "CUDAPm1 still active"
status="$(cat exit_status.txt)"
case "$status" in ''|*[!0-9]*) fail "non-numeric exit status";; esac
if [ "$status" -ne 0 ]; then
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    premature="premature-completion-capture-$stamp"
    mkdir "$premature" || fail "cannot create premature capture directory"
    python3 classify_cudapm1_result.py run.log --exponent 332228213 \
        --b1 1495000 --b2 32142500 --exit-status "$status" \
        --receipt "$premature/completion-receipt.json" \
        --factor-certificate "$premature/factor-certificate.json" \
        > "$premature/completion-classifier.stdout"
    sha256sum "$premature/completion-receipt.json" \
        "$premature/completion-classifier.stdout" exit_status.txt run.log run.time \
        > "$premature/completion-provenance.sha256"
    echo "premature failure captured; waiting for guarded resume"
    exit 0
fi
python3 classify_cudapm1_result.py run.log --exponent 332228213 \
    --b1 1495000 --b2 32142500 --exit-status "$status" \
    --receipt completion-receipt.json --factor-certificate factor-certificate.json \
    > completion-classifier.stdout
sha256sum completion-receipt.json completion-classifier.stdout exit_status.txt run.log run.time \
    > completion-provenance.sha256
sha256sum completion-receipt.json > completion-receipt.sha256
