# Exhaustive prime-stream construction

## Result

`tools/prime_stream.py --forever` is a constructive program that finds every
prime number in increasing order.  “All” has its precise computable meaning:
for each particular prime `q`, the program reaches and prints `q` after finite
time.  The complete infinite output cannot exist at a finite time or occupy a
finite file.

The implementation uses consecutive finite segments.  In a segment `[L,H]`,
it marks every multiple of every prime at most `floor(sqrt(H))`.  Every
composite `n <= H` has a prime divisor at most `sqrt(n) <= sqrt(H)`, so it is
marked.  Conversely, an unmarked integer greater than one has no possible
prime divisor at most its square root and is therefore prime.  Consecutive
segments cover every integer from the requested starting point, establishing
soundness and completeness of the lazy stream.

The separate `verify_prime_stream.py` reconstructs the prefix through one
million with a deliberately different dense-sieve implementation.  It checks
all 78,498 values, the final value 999,983, and rejection of a deleted value.

## Why this does not jump to the EFF target

Exhaustive enumeration is still ordered search.  Reaching a 100-million-digit
prime by printing every smaller prime would require traversing roughly
`10^100000000 / (100000000 ln(10))` primes before the target scale.  This is
incomparably worse than testing sparse, certificate-friendly special forms.

The missing invention is therefore not an “all primes” generator; that is now
both mathematically standard and locally implemented.  A useful shortcut would
need to accept a size `D`, directly emit a `D`-digit integer and a compact
deterministic primality certificate, and have total measured construction plus
verification work below the current special-form route.  No such target-scale
extractor is proved here.

## Reproduction

```sh
python3 tools/prime_stream.py --until 100
python3 verify_prime_stream.py
python3 tools/prime_stream.py --forever
```

The last command intentionally does not terminate; stop it after retaining the
desired prefix.  Resume strictly after the last emitted prime with `--from`.
