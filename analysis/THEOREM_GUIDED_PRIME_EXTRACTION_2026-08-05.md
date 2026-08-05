# Theorem-guided prime extraction: what would actually remove the search

## Direct answer

An incremental sieve is already an algorithm that emits every prime, exactly
once, forever.  It cannot finish because the primes are infinite, and reaching
a 100-million-digit input by enumeration would require traversing an interval
whose scale is about `10^100000000`.

Near a 100-million-digit integer, the prime number theorem predicts prime
density about

```
1 / log(10^100000000) = 1 / 230258509.299...
```

or approximately one prime per 115 million odd generic candidates.  Sieving
and special algebraic forms improve the engineering, but an existence theorem
does not identify which candidate is prime.

## Why a universal polynomial is not the missing extractor

No nonconstant integer polynomial can take prime absolute values at every
integer input.  Let `f(m)=c` with `|c|>1`.  For every integer `t`,

```
f(m + t*c) = f(m) (mod c) = 0 (mod c).
```

For sufficiently large `t`, the absolute value exceeds `|c|`, so that value is
composite.  Formulas involving a specially selected real constant can encode
an existing prime sequence, but computing the constant then contains the very
prime-selection work we wanted to avoid.

Euclid's construction similarly proves that the product of known primes plus
one has a new prime divisor; it does not say the whole number is prime or
extract its divisor.  Factoring the constructed integer becomes the hard step.

## The useful certificate theorem

Pocklington's theorem is a genuine route to construction.  Suppose

```
N - 1 = F * R,
```

the complete factorization of `F` is known, and `F > sqrt(N)`.  If suitable
modular-exponentiation and gcd conditions hold for every prime factor of `F`,
then `N` is prime.  This permits a recursive generator:

1. Begin with small certified primes.
2. Form a fully factored `F` from them.
3. Search `N = k*F + 1` with `k < F`, so `F > sqrt(N)` can hold.
4. Test Pocklington witnesses and retain a successful certified `N`.
5. Repeat until the certificate reaches 100 million digits.

Proth's theorem is an especially compact instance for
`N = k*2^n + 1`, `k < 2^n`: one successful witness congruence is already a
deterministic certificate.

This removes a separate probable-prime-then-proof pass.  It does not currently
remove candidate selection: finding a successful `k` still has prime-density
cost, and each target-scale witness uses a target-scale modular exponentiation.

## The research target that would be a real shortcut

The needed result is not merely “there exists a prime in this interval.”  A
qualifying extraction theorem would provide an explicitly computable sequence
`N(d)` such that:

- `N(d)` has at least `d` decimal digits;
- `N(d)` is prime for the target `d`, unconditionally;
- a compact certificate is generated along with `N(d)`;
- neither the definition nor evaluation hides prior prime tables, an oracle,
  an unproved conjecture, exhaustive interval search, or target-size factoring;
- total target computation materially beats one Mersenne PRP plus deterministic
  Lucas-Lehmer verification.

Producing and proving such a construction would itself be a major number-theory
breakthrough.  Until then, recursive Pocklington/Proth is the correct theorem-led
challenger to benchmark, while factor-first plus PRP/Lucas-Lehmer remains the
measured production route.

## Current experimental consequence

The project therefore runs orthogonal work rather than a blind single test:

- a deeper P-1 pass tries to produce a short compositeness certificate quickly;
- a checkpointed PRP lane advances the exact reserved candidate concurrently;
- a target-size Pocklington/Proth implementation is admitted only if measured
  certificate-producing work beats the Mersenne lane.

None of these intermediate computations is called a prime discovery.
