# Elegant direct-prime specification

## Correction of scope

The requested object is not a stream of primes.  It is a single size-indexed
function: enter a decimal digit count `D`, and obtain one distinct `D`-digit
prime together with a deterministic certificate.  The exhaustive stream is not
counted as progress toward this objective.

## One exact equation

For every integer `D >= 2`, set

```text
L_D = 10^(D-1)
```

and define

```text
P_D = min { n in Z :
            L_D < n < 2*L_D
            and ((n-1)! + 1) mod n = 0 }.
```

This is a unique, nonheuristic specification of one particular `D`-digit
prime.  Wilson's theorem says that the congruence holds exactly for primes.
Bertrand's postulate guarantees a prime strictly between `L_D` and `2*L_D`, so
the set is nonempty.  Every member of the interval has exactly `D` decimal
digits.  Therefore `P_1000000000` is mathematically well-defined, prime, and
large enough for the billion-digit EFF threshold.

This definition is not yet a discovery.  The value of `P_D` has not been
evaluated.  The factorial congruence is a predicate, not an efficient inverse,
and the `min` operation hides the exact selection work that must be solved.
EFF explicitly requires the distinct integer and a constructive certificate;
it rejects a prime-representing theorem or equation without a specific
solution.

## The actual open obligation

The remaining problem can now be stated without ambiguity:

```text
Evaluate P_D and emit a deterministic certificate in time polynomial in D,
or provide another explicit size-indexed function F(D) with the same output
and proof guarantees.
```

Testing a supplied integer is not this problem: AKS gives unconditional
deterministic polynomial-time primality testing.  Efficiently and
deterministically constructing a canonical prime of every requested length is
a stronger search problem.  Recent unconditional pseudodeterministic work
constructs a canonical prime only for infinitely many input lengths, using a
randomized polynomial-time algorithm; it does not provide the requested
deterministic all-length evaluator.

## Proof-carrying prototype result

The retained prototype uses a recursive equation

```text
N_i = 2*r_i*N_(i-1) + 1,   N_(i-1)^2 > N_i,
```

starting from `N_0=101`.  For each accepted step it records a witness `a_i`
such that

```text
a_i^(N_i-1) = 1 mod N_i
gcd(a_i^(2*r_i) - 1, N_i) = 1.
```

Pocklington's theorem then proves `N_i` prime from the already certified
`N_(i-1)`.  Input `D=1000` produced one particular 1,000-digit prime in ten
certified steps.  Its decimal-expansion SHA-256 is

```text
28af2b4f05a4b8a79919a4694397228849c191a49d068aad8e367cb09a459271
```

Construction took 18.85 seconds and independent proof verification took 0.19
seconds in the retained run.  The final step examined 1,653 multipliers; 1,464
were removed by exact small-factor sieving and 188 by a failed Fermat
congruence before the certified multiplier was reached.

This experiment solves the proof layer but not the selector layer.  It is not
promoted as the desired formula because the multiplier was found by a
deterministic search.  A 2,000-digit scaling run was deliberately stopped when
this hidden search was recognized as the wrong research objective.

## Promotion rule

A proposed equation is promoted only if all four statements are proved:

1. `F(D)` is efficiently evaluable from `D`; no `nextprime`, least-factor,
   unbounded candidate loop, or unknown real constant hides the answer.
2. `F(D)` has at least `D` decimal digits.
3. `F(D)` is unconditionally prime.
4. The emitted certificate is independently reproducible in practical total
   work competitive with the special-form baseline.

Until those obligations are met, the active Mersenne computation remains the
only operational EFF route.  No symbolic definition is an award claim.

## Primary sources

- EFF rules: <https://www.eff.org/awards/coop/rules>
- U. Maurer, *Fast Generation of Prime Numbers and Secure Public-Key
  Cryptographic Parameters*:
  <https://crypto.ethz.ch/publications/files/Maurer95a.pdf>
- A. François and D. Naccache, *Generating Provable Primes Efficiently*:
  <https://iacr.org/archive/pkc2012/72930372/72930372.pdf>
- L. Chen et al., *Polynomial-Time Pseudodeterministic Construction of
  Primes*: <https://arxiv.org/abs/2305.15140>
- D. H. J. Polymath, *Deterministic methods to find primes*:
  <https://arxiv.org/abs/1009.3956>
