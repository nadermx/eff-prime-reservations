# Adaptive factor-first shortcut experiment

Date: 2026-08-05 UTC

## Verdict

No algebraic root shortcut was found that replaces a threshold-size
Lucas--Lehmer or deterministic special-form test.  The useful adaptation is
an **early-abort portfolio**: run independent trial factoring and Pollard P-1
on spare hardware while the fastest GPU runs the sequential primality test.
If either factor lane succeeds, its output is a tiny deterministic certificate
and the multi-day test can stop.

This does not change the expected number of candidates required to discover a
prime, and a failed factor search proves nothing about primality.  It can only
reduce the time wasted on some composite candidates.

## Why the apparent Lucas--Lehmer root shortcut closes

For `M_p = 2^p - 1`, let

```text
s_0 = 4
s_(n+1) = s_n^2 - 2 mod M_p.
```

In the quadratic ring, with `alpha = 2 + sqrt(3)`, the sequence has the closed
form

```text
s_n = alpha^(2^n) + alpha^(-2^n).
```

That expression is exact, but it does not lower the natural multiplication
depth.  Starting from `alpha`, a multiplication at most doubles the largest
reachable exponent.  Therefore the addition-chain length of `2^n` is exactly
`n`: repeated squaring attains the lower bound.  For the Lucas--Lehmer final
state, `n = p - 2`.

Trying to run the recurrence backward replaces one square with a modular
square-root problem and creates two branches at each step.  When the modulus
is composite, square-root structure can itself expose a factor; when it is
prime, selecting the unique chain leading back to `4` is the unresolved part.
It is not a deterministic shortcut.  Similarly, a tree of symbolic composed
maps grows to degree `2^n`; it can make later verification parallel, but does
not remove the sequential discovery chain.

This is a lower bound for the ordinary ring-operation/addition-chain model,
not a proof that every imaginable algorithm must take the same wall time.

## The factor certificate

For any integer `q` satisfying

```text
1 < q < 2^p - 1
2^p mod q = 1,
```

`q` is a proper divisor of `M_p`, whether or not `q` is prime.  Mersenne trial
factors for prime `p` additionally have the form `q = 2*k*p + 1` and are
`1` or `7 mod 8`.

The new dependency-free verifier checks that proof without constructing the
hundred-million-digit candidate.  Its regression fixture proves that
`12,800,849` divides `M800053`, accepts the valid certificate, and rejects a
tampered factor.

## Trial-factor measurements

The official GIMPS engineering model reports that the chance of a factor in
the one-bit interval `2^x` through `2^(x+1)` is approximately `1/x`.  This is a
heuristic, not a deterministic guarantee.  For a candidate already factored
through `2^81`, the next-bit chance is therefore about

```text
1 / 81 = 1.2345679%.
```

The local candidate-test time is 12.316283 days.  A serial trial-factor pass
that delays that test breaks even only if it costs less than

```text
12.316283 days / 81 = 3.6493 hours.
```

Official mfaktc 0.24.1 produced these measurements on the already-known
composite threshold exponent `332192831`:

| Device | Correctness gate | `2^81` to `2^82` ETA | Serial cost / break-even |
| --- | --- | ---: | ---: |
| RTX 5080, 2,047 MiB GPU sieve | 23,606 / 23,606 self-tests | 8 h 11 m | 2.242 |
| Dedicated Tesla P40 | 23,606 / 23,606 self-tests | about 25 h | 6.851 |

Increasing the RTX sieve from 256 MiB to the documented 2,047 MiB changed the
projection from 8 h 16 m to 8 h 11 m.  The factor pass remains uneconomic if it
delays the RTX test.  The P40 result is even less efficient in aggregate GPU
time.

The operational distinction is that the P40 is spare.  A 25-hour P40 pass can
run concurrently with a 12.316-day RTX PRP.  It supplies a heuristic 1.23%
chance of terminating that candidate about eleven days early without delaying
the main test.  That makes the P40 pass a rational calendar-time hedge despite
its poor serial cost ratio.

## Pollard P-1 adaptation

The preflight lead's retained public history reports only `B1=100,000` and
`B2=1,000,000`.  Pollard P-1 attacks a different property from trial
factoring: it finds a factor `q = 2*k*p + 1` when `k` is sufficiently smooth.
Its success probability depends on unproved smoothness heuristics and the
chosen bounds.

GPL CUDAPm1 0.22, isolated with CUDA 11 runtime libraries on the P40, passed
all five built-in P-1 regression cases.  On the known-composite threshold
exponent it selected a 19,208K FFT and completed 1,478 stage-1 iterations for
`B1=1000` in 31 seconds.  Its bundled MPIR final GCD then remained CPU-bound
until the 10-minute benchmark limit killed it.

The adaptation now replaces that path with system GMP.  A separately coded
checkpoint reader computed the exact 100-million-digit GCD in 111.302 seconds
and 479 MiB, returning `no_factor`.  Its synthetic-checkpoint regression also
recovers the certified factor `12,800,849` of `M800053`, so a no-factor result
is not the only tested branch.

A CUDA 12.4 rebuild linked to `libgmp.so.10` passed all five P-1 self-tests on
the P40.  Restarted from the same 41,524,204-byte target checkpoint, the
integrated binary reproduced residue `0xc13ebb34e9c28063`, returned the same
no-factor result, and exited cleanly in 2:18.63 with 655 MiB peak RSS.  The
final binary hash is
`fb23ce4e30aff26f495edb3ccf45a6c847f42e9a1d0889c3f739c36cca2b4ff7`.
The old path did not complete in 10:20, so the retained evidence establishes a
conservative **greater-than-4.47x whole-path speedup**.  The standalone GCD
comparison gives a greater-than-5.57x lower bound.

The program's printed `1.7067 ms` value is a transform timing, not a complete
P-1 iteration.  Interrupted target-size checkpoints measured complete
stage-1 iterations at 20.790--21.394 ms.  The runtime model uses those
checkpoint measurements and CUDAPm1's own source-level stage-2 work formula.
It does not make the earlier transform/iteration error.

### Corrected bound decision

The CUDAPm1 optimizer was exercised with `2^81` trial factoring and both one
and two primality tests saved.  A second model executes AutoPrimeNet's vendored
Dickman-probability code directly and subtracts the already completed
`B1=100,000`, `B2=1,000,000` pass.  The existing pass had modeled total chance
0.874%; the table therefore reports the conditional *incremental* probability
after that pass failed, not the misleading headline total.

| Plan | Bounds | Conditional incremental chance | Modeled P40 time | Conservative expected RTX calendar time gained | P40 cost / expected RTX compute saved |
| --- | --- | ---: | ---: | ---: | ---: |
| One test saved | `B1=1,495,000`, `B2=32,142,500` | 2.453% | 23.51 h | 6.67 h | 12.46 |
| Two tests saved | `B1=3,215,000`, `B2=79,571,250` | 3.421% | 51.53 h | 8.35 h | 19.58 |

All probabilities are heuristics.  The runtime includes the measured
target-size GCD and a fixed setup allowance; stage 2 remains a source-derived
projection, not a completed full-bound run.  Neither P-1 plan is economical
in aggregate GPU-equivalent work.  On an otherwise idle P40, however, the
one-test plan is the better first calendar hedge: it finishes slightly sooner
than the 25-hour `2^81..2^82` trial-factor pass and has roughly twice its
modeled incremental factor probability.  If it finds no factor, the next-bit
trial-factor pass can follow while the RTX PRP continues.

## Adapted schedule after reservation

No row below is authorized before fresh status and public reservation.

1. Record the reservation and exact candidate/status snapshot in the signed
   append-only ledger.
2. Start the fastest checkpointed RTX PRP immediately.
3. On the spare P40, run exactly the fixed one-test P-1 plan
   `B1=1,495,000`, `B2=32,142,500` in `CUDAPM1_ONE_SHOT=1` mode.  This is a
   full rerun because no compatible historical checkpoint exists; that
   duplicated cost is included in the 23.51-hour model.
4. If P-1 finds no factor, run TF `2^81..2^82` on the same spare P40.
5. If a factor is found, verify it with the independent exact-integer tool,
   publish the factor certificate, and stop the PRP cleanly.
6. If both factor lanes fail, retain their completed bounds and allow the PRP
   to continue.  A probable-prime hit still requires Lucas--Lehmer and distinct
   independent verification.

## Reproducible artifacts

- `tools/verify_mersenne_factor.py`: compact exact factor verifier
- `fixtures/mersenne_factor_M800053.json`: valid regression certificate
- `tools/plan_factor_first.py`: explicit TF heuristic/economic gate
- `tools/cudapm1_checkpoint_gcd.py`: independent system-GMP checkpoint GCD
- `tools/analyze_pminus1_upgrade.py`: historical-bound correction and runtime model
- `verify_factor_first.py`: valid/tampered certificate and planner tests
- `patches/cudapm1-system-gmp-cuda12.patch`: CUDA 12.4/system-GMP port
- `runs/mfaktc-local-threshold-probe-sieve2047-20260805T024301Z/`
- `runs/mfaktc-p40-validation-20260805T025104Z/`
- `runs/cudapm1-p40-validation-20260805T025842Z/`
- `runs/cudapm1-system-gmp-build-20260805T0340Z/`
- `runs/factor-first-analysis-20260805T0300Z/`

The probability inputs come from the GIMPS mathematics description:
<https://www.mersenne.org/various/math.php>.  mfaktc provenance is rooted at
<https://download.mersenne.ca/mfaktc/>; CUDAPm1 source is pinned from
<https://github.com/ah42/cuda-p1>.

## Qualification

This is a measured optimization and a closed invalid shortcut, not a prime
discovery.  No candidate work, probable-prime result, primality proof,
publication, or EFF claim has occurred.
