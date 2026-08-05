#!/bin/bash
# Classify the exact M332228213 P-1 terminal record; starts nothing else.

set -u
expected_directory="/root/eff-prime/runs/M332228213-pminus1-queued"
fail() { echo "refusing M332228213 completion capture: $*" >&2; exit 64; }
[ "$PWD" = "$expected_directory" ] || fail "unexpected directory"
[ -f exit_status.txt ] || fail "missing exit status"
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
if [ ! -f completion-receipt.json ]; then
    python3 classify_cudapm1_result.py run.log --exponent 332228213 \
        --b1 1495000 --b2 32142500 --exit-status "$status" \
        --receipt completion-receipt.json --factor-certificate factor-certificate.json \
        > completion-classifier.stdout
fi

# The handoff watches completion-published.txt, not the receipt itself.  This
# makes the ledger result record and all provenance part of the atomic gate.
receipt_sha="$(sha256sum completion-receipt.json | awk '{print $1}')"
classification="$(python3 -c 'import json; print(json.load(open("completion-receipt.json"))["classification"])')"
case "$classification" in
    completed_no_factor_report) ledger_event=checkpoint ;;
    verified_factor) ledger_event=result ;;
    *) fail "inadmissible zero-exit classification: $classification" ;;
esac
latest_matches="$(python3 - "$receipt_sha" "$ledger_event" <<'PY'
import json
import sys
records = [json.loads(line) for line in open("ledger/mersenne_candidates.jsonl", encoding="utf-8")]
history = [r for r in records if r.get("exponent") == 332228213]
print("yes" if history and history[-1].get("event") == sys.argv[2] and
      history[-1].get("evidence_sha256") == sys.argv[1] else "no")
PY
)"
if [ "$latest_matches" != yes ]; then
    python3 candidate_ledger.py append ledger/mersenne_candidates.jsonl \
        --event "$ledger_event" --exponent 332228213 --evidence-sha256 "$receipt_sha" \
        --note "Completed fixed-bound P-1 classification: $classification; B1=1495000, B2=32142500." \
        > ledger-classification-head.txt || fail "cannot append P-1 classification"
fi
python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl \
    > ledger-classification-verify.txt || fail "post-classification ledger invalid"
sha256sum completion-receipt.json completion-classifier.stdout exit_status.txt \
    run.log run.time ledger/mersenne_candidates.jsonl > completion-provenance.sha256
sha256sum completion-receipt.json > completion-receipt.sha256
date -u +%Y-%m-%dT%H:%M:%SZ > completion-published.txt
