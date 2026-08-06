# M332228213 deterministic proof-path readiness

Captured: 2026-08-06 01:32:20 UTC

## Result

The complete conditional proof path for the reserved second candidate

`M332228213 = 2^332228213 - 1` (100,010,658 decimal digits)

is now staged and fail-closed:

1. A complete PRPLL `PRP-3` result must be parsed with current result semantics.
2. A probable-prime classification must bind the complete power-11 proof and
   pass execution-proof verification.
3. Only that verified trigger may start deterministic Lucas--Lehmer on the
   isolated VM101 Tesla P40.
4. Only the proof-bound P40 LL result may stage a distinct CPU-only Mlucas LL
   confirmation locally.

This is a readiness result. Candidate-2 P-1, PRP, P40 LL, and Mlucas LL have
not started. There is no probable-prime result, zero terminal LL residue,
prime discovery, paper, or EFF claim.

## Target-size independent arithmetic check

Pinned Mlucas commit `4a21413` ran 100 Lucas--Lehmer iterations for the exact
candidate through three different 18,432K FFT radix decompositions. All three
reported:

- Res64 `212C377C4CC32A57`;
- residue modulo `2^35-1`: `4,446,594,139`;
- residue modulo `2^36-1`: `23,791,397,180`.

An independently written GMP program computed the exact same 100-step
recurrence directly modulo `2^332228213-1` and matched all three values. It
also emitted the complete 41,528,531-byte GMP state, SHA-256
`36d625e704698143eff37f05b894acbdf70cf3de8bec56c6b8a55e15e49ca8c3`.
The retained GMP binary returned a zero terminal residue for the complete
29-step `M31` positive control.

The three-radix Mlucas run took 11.66 seconds total and at most 687,864 KiB
resident memory. The independent exact GMP run took 1 minute 37.94 seconds
and at most 484,324 KiB. These short prefix times do not estimate a complete
candidate proof; their role is exact cross-implementation arithmetic
agreement and target-size capacity validation.

## Deployment and negative gates

On VM101 (`38.86.78.5`), the selected device was Tesla P40 UUID
`GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2`. The live `M332228177` P-1 job
remained active at 100% GPU utilization with zero restarts. Candidate-2 P-1
and PRP services remained inactive, while the PRP-to-LL path unit was enabled
and waiting. The real handoff refused an absent PRP completion marker with
exit 75, and the real LL runner refused an absent predecessor manifest with
exit 64.

Locally, the Mlucas trigger timer is enabled and waiting. Both the trigger
service and CPU LL service are inactive. The real runner refused an absent
predecessor manifest with exit 64. `CUDA_VISIBLE_DEVICES` is cleared by the
runner, preserving the distinct CPU/software confirmation boundary. No H200
was used.

## Reproduction

From the project root:

```sh
sha256sum -c runs/M332228213-proof-pipeline-20260806T0011Z/MANIFEST.sha256 \
  --ignore-missing
PYTHONDONTWRITEBYTECODE=1 python3 verify_second_candidate_proof_pipeline.py
```

From the shareable `deliverables/` directory, use:

```sh
sha256sum -c MANIFEST.sha256
PYTHONDONTWRITEBYTECODE=1 python3 \
  verifiers/verify_second_candidate_proof_pipeline.py
```

The replay checks the immutable receipt and hashes, exact target-size residue
agreement, M31 positive control, deployed/staged source bindings, service
states frozen in the receipt, real negative predecessor gates, and common
fault fixtures. It deliberately proves no terminal candidate result.
