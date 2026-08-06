#!/bin/bash
# Incrementally preserve completed M332228177 PRP proof residues off VM102.

set -euo pipefail

remote_host="${EFF_PROOF_REMOTE_HOST:-root@38.86.78.6}"
remote_ip="${EFF_PROOF_REMOTE_IP:-38.86.78.6}"
remote_run="${EFF_PROOF_REMOTE_RUN:-/root/eff-prime/runs/M332228177-prp-20260805T0450Z}"
exponent="${EFF_PROOF_EXPONENT:-332228177}"
remote_proof="${EFF_PROOF_REMOTE_PROOF:-$remote_run/work/$exponent/proof}"
backup="${EFF_PROOF_BACKUP:-/home/john/eff/runs/M332228177-prp-20260805T0450Z/proof-residues-off-vm}"
expected_bytes="${EFF_PROOF_EXPECTED_BYTES:-41528528}"
expected_total="${EFF_PROOF_EXPECTED_TOTAL:-2048}"
remote_service="${EFF_PROOF_REMOTE_SERVICE:-eff-prp-m332228177.service}"
receipt_schema="${EFF_PROOF_RECEIPT_SCHEMA:-eff.vm102-prp-proof-residue-backup.v1}"
service_unit="${EFF_PROOF_SERVICE_UNIT:-/home/john/.config/systemd/user/eff-vm102-proof-residue-backup.service}"
timer_unit="${EFF_PROOF_TIMER_UNIT:-/home/john/.config/systemd/user/eff-vm102-proof-residue-backup.timer}"
scrub_interval_seconds=21600
ssh_options=(-o BatchMode=yes -o ConnectTimeout=10)

mkdir -p "$backup"
exec 9>"$backup/.backup.lock"
if ! flock -n 9; then
    echo "proof-residue backup already active; exiting"
    exit 0
fi

eligible="$(mktemp "$backup/.eligible.XXXXXX")"
manifest_tmp="$(mktemp "$backup/.manifest.XXXXXX")"
receipt_tmp="$(mktemp "$backup/.receipt.XXXXXX")"
cleanup() {
    rm -f "$eligible" "$manifest_tmp" "$receipt_tmp"
}
trap cleanup EXIT

ssh -n "${ssh_options[@]}" "$remote_host" \
    "find '$remote_proof' -maxdepth 1 -type f -mmin +1 -printf '%f\\t%s\\n' | sort -n" \
    > "$eligible"

ledger="$backup/proof-residue-ledger.jsonl"
touch "$ledger"
copied=0

# A previous receipt binds the ledger and manifest.  Refuse to continue if
# either changed since the last successful run; never re-hash altered data and
# silently bless it as the new baseline.
if [ -s "$backup/backup-receipt.json" ]; then
    previous_manifest_sha="$(jq -er '.manifest_sha256' "$backup/backup-receipt.json")"
    previous_ledger_sha="$(jq -er '.ledger_sha256' "$backup/backup-receipt.json")"
    [ -f "$backup/MANIFEST.sha256" ] || {
        echo "previous receipt exists but manifest is missing" >&2
        exit 1
    }
    [ "$(sha256sum "$backup/MANIFEST.sha256" | cut -d ' ' -f1)" = "$previous_manifest_sha" ] || {
        echo "manifest changed since previous successful backup" >&2
        exit 1
    }
    [ "$(sha256sum "$ledger" | cut -d ' ' -f1)" = "$previous_ledger_sha" ] || {
        echo "ledger changed since previous successful backup" >&2
        exit 1
    }
fi

validate_ledger() {
    jq -se --argjson exponent "$exponent" --argjson bytes "$expected_bytes" --arg remote_ip "$remote_ip" '
        all(.[];
            (.iteration | type) == "number" and
            (.iteration | floor) == .iteration and
            .iteration >= 1 and .iteration <= $exponent and
            .bytes == $bytes and
            (.sha256 | type) == "string" and
            (.sha256 | test("^[0-9a-f]{64}$")) and
            .remote_host == $remote_ip and
            .stable_remote_before_after == true) and
        ([.[].iteration] | length) == ([.[].iteration] | unique | length)
    ' "$ledger" >/dev/null
}

validate_ledger

while IFS=$'\t' read -r name size; do
    [ -n "$name" ] || continue
    [[ "$name" =~ ^[0-9]+$ ]] || {
        echo "refusing unexpected remote proof filename: $name" >&2
        exit 1
    }
    [ "$name" -ge 1 ] && [ "$name" -le "$exponent" ] || {
        echo "refusing out-of-range proof iteration: $name" >&2
        exit 1
    }
    [ "$size" = "$expected_bytes" ] || {
        echo "refusing incomplete proof residue $name: $size bytes" >&2
        exit 1
    }

    destination="$backup/$name"
    if [ -f "$destination" ]; then
        [ "$(stat -c %s "$destination")" = "$expected_bytes" ] || {
            echo "existing off-VM proof residue has wrong size: $destination" >&2
            exit 1
        }
        ledger_hash="$(jq -rs --argjson iteration "$name" \
            '[.[] | select(.iteration == $iteration) | .sha256] | if length == 1 then .[0] else empty end' \
            "$ledger")"
        if [ -n "$ledger_hash" ]; then
            continue
        fi

        # Recover safely if a prior invocation was interrupted after the
        # immutable file was renamed but before its ledger line was committed.
        before="$(ssh -n "${ssh_options[@]}" "$remote_host" \
            "sha256sum '$remote_proof/$name'" | cut -d ' ' -f1)"
        after="$(ssh -n "${ssh_options[@]}" "$remote_host" \
            "sha256sum '$remote_proof/$name'" | cut -d ' ' -f1)"
        local_hash="$(sha256sum "$destination" | cut -d ' ' -f1)"
        [ "$before" = "$after" ] && [ "$before" = "$local_hash" ] || {
            echo "unledgered proof residue does not match stable remote: $name" >&2
            exit 1
        }
        captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '{"captured_utc":"%s","iteration":%s,"bytes":%s,"sha256":"%s","remote_host":"%s","stable_remote_before_after":true,"recovered_after_interrupted_commit":true}\n' \
            "$captured" "$name" "$expected_bytes" "$local_hash" "$remote_ip" >> "$ledger"
        copied=$((copied + 1))
        continue
    fi

    if jq -se --argjson iteration "$name" \
        'any(.[]; .iteration == $iteration)' "$ledger" >/dev/null; then
        echo "ledger names proof residue $name but the local file is missing" >&2
        exit 1
    fi

    before="$(ssh -n "${ssh_options[@]}" "$remote_host" \
        "sha256sum '$remote_proof/$name'" | cut -d ' ' -f1)"
    temporary="$(mktemp "$backup/.${name}.copy.XXXXXX")"
    if ! scp -q "${ssh_options[@]}" \
        "$remote_host:$remote_proof/$name" "$temporary"; then
        rm -f "$temporary"
        exit 1
    fi
    after="$(ssh -n "${ssh_options[@]}" "$remote_host" \
        "sha256sum '$remote_proof/$name'" | cut -d ' ' -f1)"
    local_hash="$(sha256sum "$temporary" | cut -d ' ' -f1)"
    [ "$(stat -c %s "$temporary")" = "$expected_bytes" ] || {
        rm -f "$temporary"
        echo "copied proof residue has wrong size: $name" >&2
        exit 1
    }
    [ "$before" = "$after" ] && [ "$before" = "$local_hash" ] || {
        rm -f "$temporary"
        echo "proof residue changed or mismatched during copy: $name" >&2
        exit 1
    }
    chmod 0444 "$temporary"
    mv "$temporary" "$destination"
    captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '{"captured_utc":"%s","iteration":%s,"bytes":%s,"sha256":"%s","remote_host":"%s","stable_remote_before_after":true}\n' \
        "$captured" "$name" "$expected_bytes" "$local_hash" "$remote_ip" >> "$ledger"
    copied=$((copied + 1))
done < "$eligible"

validate_ledger

# Derive the manifest from the already-recorded stable hashes.  Deliberately do
# not derive it from current file contents, which could conceal later damage.
jq -rsr 'sort_by(.iteration)[] | "\(.sha256)  \(.iteration)"' \
    "$ledger" > "$manifest_tmp"
mv "$manifest_tmp" "$backup/MANIFEST.sha256"
manifest_tmp="$(mktemp "$backup/.manifest.XXXXXX")"

file_count="$(find "$backup" -maxdepth 1 -type f -regextype posix-extended \
    -regex '.*/[0-9]+' -printf '.\n' | awk 'END { print NR + 0 }')"
ledger_count="$(jq -sr 'length' "$ledger")"
[ "$file_count" = "$ledger_count" ] || {
    echo "proof file/ledger count mismatch: files=$file_count ledger=$ledger_count" >&2
    exit 1
}

full_scrub=false
scrub_marker="$backup/.last-full-scrub"
now_epoch="$(date -u +%s)"
if [ "${FORCE_FULL_SCRUB:-0}" = 1 ] || [ ! -f "$scrub_marker" ] || \
        [ $((now_epoch - $(stat -c %Y "$scrub_marker"))) -ge "$scrub_interval_seconds" ]; then
    (cd "$backup" && sha256sum -c MANIFEST.sha256 >/dev/null)
    touch "$scrub_marker"
    full_scrub=true
fi
last_full_scrub_epoch="$(stat -c %Y "$scrub_marker")"
last_full_scrub_utc="$(date -u -d "@$last_full_scrub_epoch" +%Y-%m-%dT%H:%M:%SZ)"
# A forced scrub can finish after now_epoch was sampled above.  Sample again
# so the receipt never reports a nonsensical negative scrub age.
receipt_epoch="$(date -u +%s)"
seconds_since_full_scrub=$((receipt_epoch - last_full_scrub_epoch))

read -r active_state sub_state restarts < <(
    ssh -n "${ssh_options[@]}" "$remote_host" \
        "printf '%s\\t%s\\t%s\\n' \"\$(systemctl show '$remote_service' -p ActiveState --value)\" \"\$(systemctl show '$remote_service' -p SubState --value)\" \"\$(systemctl show '$remote_service' -p NRestarts --value)\""
)
[[ "$restarts" =~ ^[0-9]+$ ]] || {
    echo "remote service restart count is not numeric: $restarts" >&2
    exit 1
}
backed_count="$(awk 'END { print NR + 0 }' "$backup/MANIFEST.sha256")"
backed_bytes=$((backed_count * expected_bytes))
eligible_count="$(awk 'END { print NR + 0 }' "$eligible")"
manifest_sha="$(sha256sum "$backup/MANIFEST.sha256" | cut -d ' ' -f1)"
ledger_sha="$(sha256sum "$ledger" | cut -d ' ' -f1)"
captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
backup_script_sha="$(sha256sum "$0" | cut -d ' ' -f1)"
[ -f "$service_unit" ] && [ -f "$timer_unit" ] || {
    echo "installed proof-residue backup units are missing" >&2
    exit 1
}
service_unit_sha="$(sha256sum "$service_unit" | cut -d ' ' -f1)"
timer_unit_sha="$(sha256sum "$timer_unit" | cut -d ' ' -f1)"

printf '{\n  "schema": "%s",\n  "captured_utc": "%s",\n  "exponent": %s,\n  "proof_power": 11,\n  "expected_total_residues": %s,\n  "expected_residue_bytes": %s,\n  "remote_eligible_count": %s,\n  "off_vm_backed_up_count": %s,\n  "copied_this_run": %s,\n  "off_vm_backed_up_bytes": %s,\n  "manifest_sha256": "%s",\n  "ledger_sha256": "%s",\n  "backup_script_sha256": "%s",\n  "installed_service_unit_sha256": "%s",\n  "installed_timer_unit_sha256": "%s",\n  "full_scrub_this_run": %s,\n  "full_scrub_interval_seconds": %s,\n  "last_full_scrub_utc": "%s",\n  "seconds_since_full_scrub": %s,\n  "remote_service": {"active_state": "%s", "sub_state": "%s", "restarts": %s},\n  "result": "PASS",\n  "scope": "Immutable PRP proof residues only; not a PRP result or primality proof."\n}\n' \
    "$receipt_schema" "$captured" "$exponent" "$expected_total" "$expected_bytes" "$eligible_count" \
    "$backed_count" "$copied" "$backed_bytes" "$manifest_sha" "$ledger_sha" \
    "$backup_script_sha" "$service_unit_sha" "$timer_unit_sha" "$full_scrub" \
    "$scrub_interval_seconds" "$last_full_scrub_utc" \
    "$seconds_since_full_scrub" "$active_state" "$sub_state" "$restarts" > "$receipt_tmp"
mv "$receipt_tmp" "$backup/backup-receipt.json"
receipt_tmp="$(mktemp "$backup/.receipt.XXXXXX")"

echo "backed_up=$backed_count eligible=$eligible_count copied=$copied bytes=$backed_bytes"
