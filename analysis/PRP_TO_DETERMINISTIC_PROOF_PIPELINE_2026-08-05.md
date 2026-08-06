# PRP-to-deterministic-proof pipeline for M332228177

Date: 2026-08-05

## Result

The live PRP-to-proof boundary is now fail-closed and deployed. If the current
PRPLL run returns probable prime, the exact result is bound to its complete
power-11 proof file, that execution proof is verified, and only then are two
deterministic Lucas--Lehmer computations admitted:

1. PRPLL Lucas--Lehmer on VM102's Tesla P40;
2. pinned Mlucas commit `4a21413` on the local CPU, with CUDA hidden.

At the retained snapshot neither deterministic computation had started. The
live PRP was at iteration 5,340,000 with zero service restarts; VM101's P-1
stage 2 remained active. There was no PRP result, zero Lucas--Lehmer residue,
prime, publication, or award claim. The H200 was not used.

## Terminal parser defect found and repaired

The launch-era result wrapper expected an older logical record: worktype
`PRP` and an `error-code` field. The exact current source and deployed PRPLL
binary instead emit worktype `PRP-3`; the integrity condition is
`errors.gerbicz == 0`, and the terminal record carries `res2048`,
`residue-type`, and proof metadata. Left unchanged, the wrapper would have
rejected a valid result after the long computation.

The replacement parser, SHA-256
`7cb64288e184472df792af28db562415785d42fd43265338965a3349fb4484ec`,
accepts only the observed `PRP-3` format for logical PRP work. It requires:

- exactly one terminal record for exponent `332228177`;
- status `P` or `C`, exact 64- and 2,048-bit residue encodings;
- `residue-type=1` and `errors={"gerbicz":0}`;
- proof format version 1, power 4 through 13, 64-bit hash size, and MD5;
- program name `prpll`, a nonempty version, and a timestamp.

For LL it separately requires error code zero. Prime status is admissible only
with Res64 `0000000000000000`. Synthetic tests reject the old worktype,
nonzero Gerbicz errors, missing proof metadata, malformed residues, duplicate
records, and a nonzero-residue LL prime claim.

The exact parser was hot-deployed without stopping PRP at
`2026-08-05T23:36:04Z` on VM102 and into candidate 2's inactive PRP staging on
VM101. Both deployed copies match the source hash above.

## Proof-bound transition

`tools/classify_prpll_transition.py` binds the validated result to the exact
file `332228177-11.proof`. It parses the `PRP PROOF`, version 2 header,
requires the exact residue-body size, recomputes the result-specified MD5, and
retains a SHA-256 digest. The handoff then runs PRPLL's proof verifier in an
isolated directory and demands its exact success line before publishing a
transition manifest.

A composite PRP result publishes only the composite stop marker. A probable
prime result publishes a trigger for deterministic proof; it is never labeled
prime. Truncated, wrong-header, and content-tampered proof fixtures all fail.

## Deterministic proof branches

The P40 branch is pinned to GPU UUID
`GPU-a5c50372-9b4f-1496-eebf-f7220cd342fd`, PRPLL SHA-256
`04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d`,
the signed reservation, and the proof-verification manifest. It invokes
`-ll 332228177 -noclean`. Its completion receipt can say deterministic prime
only when the exact validated terminal residue is zero.

The independent branch stages pinned Mlucas binary SHA-256
`b9d89a8e1a2c2c558c86fad6ead3fd311fd93e9eb67bda1bdf8f9f98c81f3d56`
and source archive SHA-256
`7d077166c5d34869e7a08b78cb838317a2ba1a51277fb17ce79c964d987efacb`.
It uses 12 CPU threads and sets `CUDA_VISIBLE_DEVICES` empty. Its own parser
requires one exact Mlucas LL record, error code zero, no nonzero error count,
and a zero residue for prime status. The trigger polls every five minutes,
verifies every remote/local transfer hash, and resumes a checkpointed local
run after reboot without creating a duplicate.

## Real negative gates and retained state

The deployed handoff returned exit 75 because the PRP completion marker is
absent. The staged P40 LL runner returned exit 64 because its predecessor
manifest is absent. The local Mlucas runner independently returned exit 64
for the same missing predecessor. The VM102 handoff path and local Mlucas
trigger timer are enabled and waiting; both deterministic compute services
remain inactive.

The multiple-source SCP form used by the local synchronizer was executed
against VM102 and produced the exact expected runner and parser hashes. This
closes a transfer syntax risk without manufacturing a trigger.

At `2026-08-05T23:52:34Z`:

- VM102 PRP: iteration 5,340,000, 100% P40 utilization, zero restarts;
- VM101 P-1: pass group 536--642 of 960, latest displayed ETA 4:34:17;
- off-VM proof backup: 32 of 2,048 residues, 1,328,912,896 bytes;
- candidate 2 P-1 and PRP: inactive and not started;
- deterministic P40 LL and CPU Mlucas: inactive and not started.

## Replay

From the project root:

```sh
python3 verify_prpll_result_semantics.py
python3 verify_prp_to_ll_transition.py
python3 verify_mlucas_result_semantics.py
python3 verify_prp_to_ll_pipeline.py
```

The deployment receipt is
`runs/prp-to-ll-pipeline-20260805T2348Z/deployment-receipt.json`, SHA-256
`c540887dbe6ba87524f8ccbe30903339bd5a1ad378031b620e172da3fbf44838`.

## Qualification boundary

This closes a result-admission and transition-readiness gap. It does not close
the mathematical gap. `M332228177` qualifies only if a complete deterministic
Lucas--Lehmer run produces zero, an independent run confirms it, the evidence
is reviewed, and a refereed paper is published. None of those terminal events
has occurred.
