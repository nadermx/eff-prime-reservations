# Independent Mersenne reservation

This repository publicly reserves three exact exponents, and no surrounding
range, for an independent search by Johnathan Nader (`@nadermx`):

- active candidate `M332228177 = 2^332228177-1`, extended through
  `2027-01-15T04:06:06Z`;
- queued candidate `M332228213 = 2^332228213-1`, reserved through
  `2027-01-31T22:05:49Z`;
- backup candidate `M332228447 = 2^332228447-1`, reserved through
  `2027-01-31T23:16:08Z`.

The second candidate cannot start until the first candidate's active P-1 pass
has been independently classified, the assigned P40 is idle, and a fresh
post-publication official status gate passes.  Its reviewed first action is a
fixed deeper P-1 pass, not cold PRP or further TF on the first candidate.
The third candidate cannot start until a prior P40 lane is terminal and idle,
a fresh official status gate passes, and a new measured allocation selects it.
Its retained deep P-1 model is heuristic planning, not work authorization.

The reservation was prepared only after a fresh official status fetch reported
no known factor, no primality result, and no assignment record.  The complete
raw snapshot, local hash-chain ledger, fixed factor-first plan, signer public
key, detached SSH signature, and SHA-256 manifest are included.  Further fresh
status gates were recorded immediately before each independent compute lane.

Current public progress:

- fixed-bound P-1 began on VM101 at `2026-08-05T04:13:25Z`;
- a second Tesla P40 reproduced the independent 10,000-iteration PRP residue;
- the fresh VM102 PRP gate at `2026-08-05T04:50:04Z` remained unassigned with
  no known factor;
- full checkpointed PRP began at `2026-08-05T04:50:53Z`;
- its iteration-2,000 checkpoint was copied off-VM and SHA-256 verified.
- P-1 later reached iteration 150,000, and its newer recovery checkpoint was
  also copied off-VM and SHA-256 verified.
- a fail-closed completion watcher is waiting for the P-1 exit record; it
  verifies any reported factor and cannot launch follow-on computation.
- the current `PRP-3` terminal format was source-audited and its hardened
  exact-result parser was deployed by SHA-256 without interrupting PRP;
- a proof-bound probable-prime transition, deterministic P40
  Lucas--Lehmer branch, and distinct CPU/Mlucas branch are staged behind real
  negative predecessor gates. At the retained receipt PRP was at iteration
  5,340,000 and neither deterministic branch had started.
- the same proof-bound deterministic path is now staged for queued
  `M332228213`; three exact-size Mlucas radix sets and an independent GMP
  recurrence matched after 100 LL steps on Res64 `212C377C4CC32A57`, while
  every real absent-predecessor gate refused and candidate-2 arithmetic
  remained unstarted.

These are active search records, not a probable-prime result, deterministic
Lucas-Lehmer proof, discovery announcement, or award claim.

The accompanying research bundle also includes a lazy segmented prime stream
and independent million-prefix verifier.  It constructively enumerates every
prime eventually, but makes no claim to jump to the 100-million-digit scale.

The corrected direct-prime lane separately defines a canonical `D`-digit prime
and retains a real 1,000-digit, ten-step Pocklington construction with an
independent verifier.  Its final multiplier was still selected by search, so it
is proof-layer evidence rather than a no-search EFF-scale constructor.

This is a non-duplication notice, not a claim of primality, discovery,
coordinator assignment, award eligibility, or ownership of the integer.  The
search is independent and does not submit work to PrimeNet.

Verify the detached signature from the repository root:

```sh
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation \
  -s reservation/M332228177.json.sig \
  < reservation/M332228177.json
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation-extension \
  -s reservation/M332228177-extension-20260805.json.sig \
  < reservation/M332228177-extension-20260805.json
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation \
  -s reservation/M332228213.json.sig \
  < reservation/M332228213.json
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation \
  -s reservation/M332228447.json.sig \
  < reservation/M332228447.json
sha256sum -c MANIFEST.sha256
```

The exact scopes and safety gates are machine-readable in the three reservation
documents.
