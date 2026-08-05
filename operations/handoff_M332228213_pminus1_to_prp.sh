#!/bin/bash
# Start M332228213 PRP only after its exact P-1 pass completes with no factor.

set -u
root="/root/eff-prime"
p1="$root/runs/M332228213-pminus1-queued"
prp="$root/runs/M332228213-prp-queued"
authority="https://github.com/nadermx/eff-prime-reservations/commit/83b3472f12e7d571a6aa43bc478154e42b604289"
fail() { echo "refusing M332228213 P-1-to-PRP handoff: $*" >&2; exit 64; }
[ "$PWD" = "$prp" ] || fail "unexpected directory"
[ -f "$p1/completion-published.txt" ] || fail "P-1 completion is not atomically published"
[ -f "$p1/completion-receipt.json" ] || fail "P-1 receipt absent"
if systemctl is-active --quiet eff-pm1-m332228213.service || \
   systemctl is-active --quiet eff-pm1-m332228213-resume.service; then
    fail "P-1 service remains active"
fi
pgrep -f '[C]UDAPm1-system-gmp' >/dev/null && fail "CUDAPm1 remains active"

classification="$(python3 -c 'import json; print(json.load(open("'"$p1"'/completion-receipt.json"))["classification"])')"
if [ "$classification" = "verified_factor" ]; then
    python3 - <<PY || fail "P-1 factor verification"
import json
r = json.load(open("$p1/completion-receipt.json", encoding="utf-8"))
c = json.load(open("$p1/factor-certificate.json", encoding="utf-8"))
q = int(c["factor"])
assert r["exponent"] == c["exponent"] == 332228213
assert r["classification"] == "verified_factor"
assert pow(2, 332228213, q) == 1
PY
    date -u +%Y-%m-%dT%H:%M:%SZ > NOT_STARTED_VERIFIED_FACTOR.txt
    echo "verified factor stops M332228213 before PRP"
    exit 0
fi
[ "$classification" = "completed_no_factor_report" ] || \
    fail "P-1 did not produce an admissible terminal classification"
python3 - <<PY || fail "P-1 no-factor receipt"
import json
r = json.load(open("$p1/completion-receipt.json", encoding="utf-8"))
assert r["exponent"] == 332228213
assert r["b1"] == 1495000 and r["b2"] == 32142500
assert r["program_exit_status"] == 0
PY

mkdir predecessor || fail "predecessor directory already exists"
cp "$p1/completion-receipt.json" predecessor/
cp "$p1/completion-published.txt" predecessor/
python3 candidate_preflight.py 332228213 --evidence-dir preflight \
    > preflight.stdout || fail "fresh official status fetch"
preflight_sha="$(sha256sum preflight/preflight.json | awk '{print $1}')"
python3 - <<'PY' || fail "fresh official status ineligible"
import json
x = json.load(open("preflight/preflight.json", encoding="utf-8"))
assert x["exponent"] == 332228213
assert x["eligible_for_manual_reservation_review"] is True
assert x["assignment_record_present"] is False
assert x["published_status"] == "untested_no_known_factor"
PY
cp "$p1/ledger/mersenne_candidates.jsonl" ledger/mersenne_candidates.jsonl
python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl >/dev/null || \
    fail "copied P-1 ledger invalid"
python3 candidate_ledger.py append ledger/mersenne_candidates.jsonl \
    --event status_snapshot --exponent 332228213 \
    --evidence-sha256 "$preflight_sha" \
    --note "Fresh official M332228213 status immediately before post-P-1 PRP lane." \
    > ledger-status-head.txt || fail "status append"
python3 candidate_ledger.py append ledger/mersenne_candidates.jsonl \
    --event lane_started --exponent 332228213 \
    --evidence-sha256 "$preflight_sha" --authority-reference "$authority" \
    --note "Authorized checkpointed PRP/proof lane on VM101 after completed no-factor P-1." \
    > ledger-lane-head.txt || fail "lane append"
python3 candidate_ledger.py verify ledger/mersenne_candidates.jsonl > ledger-verify.txt || \
    fail "post-append ledger invalid"
./run.sh --preflight-only > handoff-preflight.stdout || fail "PRP preflight"
date -u +%Y-%m-%dT%H:%M:%SZ > handoff_utc.txt
sha256sum preflight/* predecessor/* ledger/mersenne_candidates.jsonl \
    reservation/* prpll run.sh verify_prpll_result.py > handoff-provenance.sha256
systemctl start eff-prp-m332228213.service || fail "PRP systemd start"
sleep 5
systemctl is-active --quiet eff-prp-m332228213.service || fail "PRP did not remain active"
nvidia-smi --query-gpu=timestamp,name,uuid,utilization.gpu,memory.used,temperature.gpu \
    --format=csv,noheader > handoff-gpu.csv
echo "M332228213 PRP started after completed P-1 no-factor result"
