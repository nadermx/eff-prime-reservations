#!/bin/bash
# Configure the shared immutable-residue backup engine for VM101/M332228213.

set -euo pipefail
export EFF_PROOF_REMOTE_HOST="root@38.86.78.5"
export EFF_PROOF_REMOTE_IP="38.86.78.5"
export EFF_PROOF_REMOTE_RUN="/root/eff-prime/runs/M332228213-prp-queued"
export EFF_PROOF_EXPONENT="332228213"
export EFF_PROOF_BACKUP="/home/john/eff/runs/M332228213-prp-queued/proof-residues-off-vm"
export EFF_PROOF_EXPECTED_BYTES="41528528"
export EFF_PROOF_EXPECTED_TOTAL="2048"
export EFF_PROOF_REMOTE_SERVICE="eff-prp-m332228213.service"
export EFF_PROOF_RECEIPT_SCHEMA="eff.vm101-M332228213-prp-proof-residue-backup.v1"
export EFF_PROOF_SERVICE_UNIT="/home/john/.config/systemd/user/eff-vm101-M332228213-proof-residue-backup.service"
export EFF_PROOF_TIMER_UNIT="/home/john/.config/systemd/user/eff-vm101-M332228213-proof-residue-backup.timer"

# It is safe to install this timer before the queued PRP begins.  Until the
# handoff starts the exact service and creates its proof directory, this is a
# successful no-op rather than an alarming backup failure.
if ! ssh -n -o BatchMode=yes -o ConnectTimeout=10 "$EFF_PROOF_REMOTE_HOST" \
    "systemctl is-active --quiet '$EFF_PROOF_REMOTE_SERVICE' && test -d '$EFF_PROOF_REMOTE_RUN/work/$EFF_PROOF_EXPONENT/proof'"; then
    echo "waiting: VM101 M332228213 PRP proof directory is not active yet"
    exit 0
fi

exec /home/john/eff/scripts/backup_vm102_prp_proof_residues.sh
