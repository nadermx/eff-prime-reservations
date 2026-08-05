#!/bin/bash
# Fail-closed VM101 handoff from classified M332228177 P-1 to M332228213 P-1.

set -u
root="/root/eff-prime"
prior="$root/runs/M332228177-pminus1-20260805T0412Z"
next="$root/runs/M332228213-pminus1-queued"
authority="https://github.com/nadermx/eff-prime-reservations/commit/83b3472f12e7d571a6aa43bc478154e42b604289"

fail() { echo "refusing M332228213 handoff: $*" >&2; exit 64; }
[ "$PWD" = "$next" ] || fail "unexpected directory"
[ -f "$prior/completion-receipt.json" ] || fail "predecessor is not classified"
if systemctl is-active --quiet eff-pm1-m332228177.service || \
   systemctl is-active --quiet eff-pm1-m332228177-resume.service; then
    fail "predecessor P-1 service is still active"
fi
pgrep -f '[C]UDAPm1-system-gmp' >/dev/null && fail "CUDAPm1 is still active"
[ "$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -n 1)" = \
  "GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2" ] || fail "unexpected GPU"

mkdir predecessor || fail "predecessor evidence directory already exists"
cp "$prior/completion-receipt.json" predecessor/
[ -f "$prior/factor-certificate.json" ] && cp "$prior/factor-certificate.json" predecessor/
python3 - <<'PY' || fail "predecessor receipt"
import json
r = json.load(open("predecessor/completion-receipt.json", encoding="utf-8"))
assert r["exponent"] == 332228177
assert r["classification"] in {"completed_no_factor_report", "verified_factor"}
if r["classification"] == "completed_no_factor_report":
    assert r["program_exit_status"] == 0
else:
    c = json.load(open("predecessor/factor-certificate.json", encoding="utf-8"))
    q = int(c["factor"])
    assert c["exponent"] == 332228177 and pow(2, 332228177, q) == 1
PY

python3 candidate_preflight.py 332228213 --evidence-dir preflight \
    > preflight.stdout || fail "fresh official preflight fetch"
preflight_sha="$(sha256sum preflight/preflight.json | awk '{print $1}')"
python3 - <<'PY' || fail "fresh official status is ineligible"
import json
x = json.load(open("preflight/preflight.json", encoding="utf-8"))
assert x["exponent"] == 332228213
assert x["eligible_for_manual_reservation_review"] is True
assert x["assignment_record_present"] is False
assert x["published_status"] == "untested_no_known_factor"
assert x["no_factor_to_bits"] >= 81 and x["tf_target_bits"] <= 81
assert x["pminus1_current_b1"] == 100000 and x["pminus1_current_b2"] == 1000000
PY

python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl >/dev/null || \
    fail "staged ledger is invalid"
python3 candidate_ledger.py append ledger/mersenne_candidates.jsonl \
    --event status_snapshot --exponent 332228213 \
    --evidence-sha256 "$preflight_sha" \
    --note "Fresh post-reservation VM101 start gate; exact official snapshot retained on the compute host." \
    > ledger-status-head.txt || fail "cannot append start status"
python3 candidate_ledger.py append ledger/mersenne_candidates.jsonl \
    --event work_started --exponent 332228213 \
    --evidence-sha256 "$preflight_sha" --authority-reference "$authority" \
    --note "Authorized fixed-bound P-1 start on VM101 Tesla P40; B1=1495000, B2=32142500." \
    > ledger-work-head.txt || fail "cannot append work authorization"
python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl \
    > ledger-verify.txt || fail "post-append ledger is invalid"

./run.sh --preflight-only > handoff-preflight.stdout || fail "arithmetic launch preflight"
date -u +%Y-%m-%dT%H:%M:%SZ > handoff_utc.txt
sha256sum preflight/* predecessor/* ledger/mersenne_candidates.jsonl \
    reservation/* run.sh resume.sh capture-completion.sh > handoff-provenance.sha256
systemctl start eff-pm1-m332228213.service || fail "systemd start"
sleep 5
systemctl is-active --quiet eff-pm1-m332228213.service || \
    fail "new P-1 service did not remain active"
nvidia-smi --query-gpu=timestamp,name,uuid,utilization.gpu,memory.used,temperature.gpu \
    --format=csv,noheader > handoff-gpu.csv
echo "M332228213 P-1 handoff started"
