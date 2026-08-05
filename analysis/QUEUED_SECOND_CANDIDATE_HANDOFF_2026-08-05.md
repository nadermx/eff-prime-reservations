# Queued second qualifying candidate and measured P40 handoff

Date: 2026-08-05 UTC

## Result

`M332228213 = 2^332228213-1` is now publicly reserved as an exact second
candidate. It has 100,010,658 decimal digits. It is queued, not running, and
has no PRP or primality result.

The signed reservation is published at
<https://github.com/nadermx/eff-prime-reservations/commit/83b3472f12e7d571a6aa43bc478154e42b604289>.
The signed commit and detached reservation signature both use Johnathan
Nader's established Ed25519 identity. The public ledger/manifest follow-up is
commit `dfb78cf245655e7e40331498e93c213673be04cd`.

The first ledger append for this candidate accidentally transcribed the wrong
evidence digest. Nothing had been reserved or computed. Because the ledger is
append-only, sequence 17 was retained and sequence 18 explicitly corrected it
to the verified preflight JSON SHA-256
`255846f6539d9141bf310898715a06c517ada27862967f0efc7c6693a3e1de9a`.
The signed reservation binds only to the corrected record.

## Measured allocation decision

At the retained VM102 rate of 12,169 microseconds per iteration, the current
candidate had 46.12 modeled PRP days remaining and a cold PRP for the second
candidate models to 46.79 days.

The next TF bit on the current candidate costs 25.00 measured P40-hours. Its
`1/81` heuristic factor probability yields only 13.51 expected current-PRP
hours saved, or negative 11.49 net P40-hours. It is rejected.

For the second candidate, repeating the already measured P-1 upgrade at
`B1=1,495,000`, `B2=32,142,500` costs 23.51 modeled P40-hours. After its
historical shallow pass, the isolated Dickman model assigns a 2.4528%
conditional factor probability. Against a 46.79-day P40 PRP, that is 27.55
expected hours saved, or positive 4.03 net P40-hours. The selected schedule is
therefore deeper P-1 on the second candidate, followed by PRP only if no factor
is found.

These probabilities are heuristic. They choose resource order; they prove
nothing about either number.

## Fail-closed deployment

VM101 retains the active recovered P-1 for `M332228177` at 100% Tesla P40
utilization. The second-candidate arithmetic service is inactive. A separate
watcher can hand over the P40 only after the predecessor has a classified
terminal receipt.

At handoff it must independently pass all of these gates:

1. the predecessor service is inactive and its exact result is either a
   zero-exit no-factor report or an independently verified factor;
2. the expected P40 UUID is idle and no CUDAPm1 process exists;
3. a new official status fetch reports no assignment, result, or known factor;
4. that status is no more than 15 minutes old;
5. the detached exact-exponent reservation signature and expiry pass;
6. the append-only ledger ends in `reservation`, fresh `status_snapshot`, and
   `work_started`, all bound to the same evidence hash and public authority;
7. the binary and work line match their pinned SHA-256 values.

The obsolete billion-integrity and current-candidate TF paths on VM101 are
disabled. Disabling them did not stop or restart either live computation. The
completion watcher itself was corrected from `PathExists` to `PathChanged` so
the recovered P-1's final overwrite cannot be missed.

The staging receipt at 22:14:05 UTC records the predecessor active, the queued
service inactive, both new watchers waiting, both obsolete paths disabled, and
the exact remote hashes. No fresh start-status directory existed yet, which is
intentional: it must be created at the actual handoff, not hours early.

## Qualification boundary

This is a throughput and non-duplication breakthrough, not a mathematical
one. Neither candidate is known prime. A PRP `P` result would still require a
complete Lucas--Lehmer zero residue, distinct verification, refereed
publication, and the EFF claim process.
