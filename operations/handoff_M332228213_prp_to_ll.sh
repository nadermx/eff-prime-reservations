#!/bin/bash
# Verify an M332228213 PRP proof and admit LL only after a probable-prime hit.

set -euo pipefail

root="/root/eff-prime"
prp="$root/runs/M332228213-prp-queued"
ll="$root/runs/M332228213-ll-queued"
expected_exponent=332228213
expected_gpu_uuid="GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2"
expected_prpll_sha256="04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d"
expected_verifier_sha256="7cb64288e184472df792af28db562415785d42fd43265338965a3349fb4484ec"
expected_classifier_sha256="5af7a4363c0d70bfaa96a484e3ce0bb39f055f907229bc9e941ebea7e7f86166"

fail() { echo "M332228213 PRP-to-LL handoff refused: $*" >&2; exit 75; }

[ ! -e "$prp/COMPOSITE_PRP_PUBLISHED.txt" ] || exit 0
if [ -e "$prp/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt" ]; then
    if [ ! -e "$ll/completion-published.txt" ] && \
       [ "$(systemctl is-active eff-ll-m332228213.service)" = inactive ]; then
        systemctl start eff-ll-m332228213.service
    fi
    exit 0
fi

[ -e "$prp/completed_utc.txt" ] || fail "PRP completion marker absent"
[ "$(systemctl is-active eff-prp-m332228213.service)" = inactive ] || fail "PRP service has not exited"
if pgrep -f '(^|/)[p]rpll( |$)' >/dev/null; then fail "PRPLL process is still active"; fi
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n1)" = "$expected_gpu_uuid" ] || fail "GPU UUID mismatch"
[ "$(sha256sum "$prp/prpll" | awk '{print $1}')" = "$expected_prpll_sha256" ] || fail "PRPLL hash mismatch"
[ "$(sha256sum "$prp/verify_prpll_result.py" | awk '{print $1}')" = "$expected_verifier_sha256" ] || fail "result verifier hash mismatch"
[ "$(sha256sum "$prp/classify_prpll_transition.py" | awk '{print $1}')" = "$expected_classifier_sha256" ] || fail "transition classifier hash mismatch"

temporary="$prp/transition-work"
mkdir -p "$temporary"
rm -f "$temporary/validated-result.json" "$temporary/transition-receipt.json"
python3 "$prp/verify_prpll_result.py" "$prp/work/results-0.txt" \
    --exponent "$expected_exponent" --worktype PRP > "$temporary/validated-result.json" || fail "PRP result validation failed"
cmp -s "$temporary/validated-result.json" "$prp/validated-result.json" || fail "wrapper and handoff validated results differ"

proof_power="$(python3 -c 'import json; print(json.load(open("'"$prp"'/validated-result.json"))["proof"]["power"])')"
[ "$proof_power" = 11 ] || fail "unexpected proof power: $proof_power"
proof="$prp/work/proof/${expected_exponent}-${proof_power}.proof"
python3 "$prp/classify_prpll_transition.py" \
    "$prp/validated-result.json" "$proof" \
    --expected-exponent "$expected_exponent" --expected-proof-power "$proof_power" \
    --output "$temporary/transition-receipt.json" || fail "proof binding failed"

verify_dir="$temporary/proof-verification"
mkdir -p "$verify_dir"
rm -f "$verify_dir/gpuowl-0.log" "$verify_dir/stdout.txt" "$verify_dir/time.txt"
set +e
/usr/bin/time -v "$prp/prpll" -dir "$verify_dir" -device 0 -use NO_ASM \
    -verify "$proof" > "$verify_dir/stdout.txt" 2> "$verify_dir/time.txt"
verify_status=$?
set -e
[ "$verify_status" -eq 0 ] || fail "proof verifier exited $verify_status"
grep -F "proof '$proof' verified" "$verify_dir/gpuowl-0.log" >/dev/null || fail "proof verification success line absent"
if grep -F "failed" "$verify_dir/gpuowl-0.log" >/dev/null; then fail "proof verifier reported failure"; fi

python3 - "$temporary/transition-receipt.json" "$proof" "$verify_dir/gpuowl-0.log" "$verify_dir/time.txt" > "$temporary/proof-verification-receipt.json.tmp" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

transition_path, proof_path, log_path, time_path = sys.argv[1:]
transition = json.load(open(transition_path, encoding="utf-8"))
receipt = {
    "schema": "eff.prpll-proof-execution-verification.v1",
    "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "exponent": transition["exponent"],
    "proof_sha256": digest(proof_path),
    "proof_verification_log_sha256": digest(log_path),
    "proof_verification_time_sha256": digest(time_path),
    "gpu_uuid": "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2",
    "program_sha256": "04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d",
    "result": "PASS",
    "scope": "M332228213 PRP execution-proof verification; not a deterministic primality proof.",
}
print(json.dumps(receipt, indent=2, sort_keys=True))
PY
mv "$temporary/proof-verification-receipt.json.tmp" "$temporary/proof-verification-receipt.json"

mkdir -p "$ll/predecessor"
install -m 0644 "$prp/validated-result.json" "$ll/predecessor/validated-prp-result.json"
install -m 0644 "$temporary/transition-receipt.json" "$ll/predecessor/transition-receipt.json"
install -m 0644 "$temporary/proof-verification-receipt.json" "$ll/predecessor/proof-verification-receipt.json"
sha256sum "$proof" > "$ll/predecessor/prp-proof.sha256"
(cd "$ll/predecessor" && sha256sum validated-prp-result.json transition-receipt.json proof-verification-receipt.json prp-proof.sha256 > MANIFEST.sha256)

classification="$(python3 -c 'import json; print(json.load(open("'"$temporary"'/transition-receipt.json"))["classification"])')"
if [ "$classification" = verified_composite_prp ]; then
    date -u +%Y-%m-%dT%H:%M:%SZ > "$prp/COMPOSITE_PRP_PUBLISHED.txt.tmp"
    mv "$prp/COMPOSITE_PRP_PUBLISHED.txt.tmp" "$prp/COMPOSITE_PRP_PUBLISHED.txt"
    exit 0
fi
[ "$classification" = probable_prime_trigger ] || fail "unknown classification: $classification"
date -u +%Y-%m-%dT%H:%M:%SZ > "$prp/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt.tmp"
mv "$prp/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt.tmp" "$prp/PROBABLE_PRIME_TRIGGER_PUBLISHED.txt"
systemctl start eff-ll-m332228213.service
