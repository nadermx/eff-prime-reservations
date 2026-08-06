#!/bin/bash
# Classify VM102 M332228447 P-1; canonical ledger append remains on VM101.

set -u
expected_directory="/root/eff-prime/runs/M332228447-pminus1-factor-branch"
fail() { echo "refusing M332228447 VM102 completion capture: $*" >&2; exit 64; }
[ "$PWD" = "$expected_directory" ] || fail "unexpected directory"
[ -f exit_status.txt ] || fail "missing exit status"

completion_metadata_ready() {
    if [ -f resume-checkpoint-metadata.json ]; then
        [ -f resume_ended_utc.txt ] && [ resume_ended_utc.txt -nt exit_status.txt ] && \
            [ -f resume_after_gpu.csv ] && [ resume_after_gpu.csv -nt exit_status.txt ]
    else
        [ -f ended_utc.txt ] && [ ended_utc.txt -nt exit_status.txt ] && \
            [ -f after_gpu.csv ] && [ after_gpu.csv -nt exit_status.txt ]
    fi
}
completion_ready=no
for _ in $(seq 0 30); do
    if ! pgrep -f '[C]UDAPm1-system-gmp' >/dev/null && \
       ! systemctl is-active --quiet eff-pm1-m332228447-vm102.service && \
       ! systemctl is-active --quiet eff-pm1-m332228447-vm102-resume.service && \
       completion_metadata_ready; then
        completion_ready=yes
        break
    fi
    sleep 1
done
[ "$completion_ready" = yes ] || fail "terminal process/service/metadata did not settle"
if [ -f resume-checkpoint-metadata.json ]; then
    terminal_metadata=(resume_ended_utc.txt resume_after_gpu.csv)
else
    terminal_metadata=(ended_utc.txt after_gpu.csv)
fi
status="$(cat exit_status.txt)"
case "$status" in ''|*[!0-9]*) fail "non-numeric exit status";; esac
if [ "$status" -ne 0 ]; then
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    premature="premature-completion-capture-$stamp"
    mkdir "$premature" || fail "cannot create premature capture directory"
    python3 classify_cudapm1_result.py run.log --exponent 332228447 \
        --b1 1495000 --b2 32142500 --exit-status "$status" \
        --receipt "$premature/completion-receipt.json" \
        --factor-certificate "$premature/factor-certificate.json" \
        > "$premature/completion-classifier.stdout"
    sha256sum "$premature/completion-receipt.json" \
        "$premature/completion-classifier.stdout" exit_status.txt run.log run.time \
        "${terminal_metadata[@]}" \
        > "$premature/completion-provenance.sha256"
    echo "premature failure captured; waiting for guarded resume"
    exit 0
fi
if [ ! -f completion-receipt.json ]; then
    python3 classify_cudapm1_result.py run.log --exponent 332228447 \
        --b1 1495000 --b2 32142500 --exit-status "$status" \
        --receipt completion-receipt.json --factor-certificate factor-certificate.json \
        > completion-classifier.stdout
fi
classification="$(python3 -c 'import json; print(json.load(open("completion-receipt.json"))["classification"])')"
case "$classification" in completed_no_factor_report|verified_factor) ;; 
    *) fail "inadmissible zero-exit classification: $classification" ;;
esac
receipt_sha="$(sha256sum completion-receipt.json | awk '{print $1}')"
python3 - "$receipt_sha" "$classification" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
doc = {
    "schema": "eff.M332228447-pminus1-terminal-sync-required.v1",
    "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "exponent": 332228447,
    "classification": sys.argv[2],
    "completion_receipt_sha256": sys.argv[1],
    "canonical_ledger_host": "38.86.78.5",
    "canonical_ledger_appended": False,
    "follow_on_work_allowed": False,
}
tmp = "terminal-sync-required.json.tmp"
open(tmp, "w", encoding="utf-8").write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
os.replace(tmp, "terminal-sync-required.json")
PY
sha256sum completion-receipt.json completion-classifier.stdout exit_status.txt \
    run.log run.time "${terminal_metadata[@]}" terminal-sync-required.json \
    > completion-provenance.sha256
sha256sum completion-receipt.json > completion-receipt.sha256
date -u +%Y-%m-%dT%H:%M:%SZ > completion-published.txt
