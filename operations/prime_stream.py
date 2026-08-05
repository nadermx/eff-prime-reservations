#!/usr/bin/env python3
"""Emit the prime numbers in increasing order with a segmented sieve.

With --forever this is a lazy exhaustive enumerator: every prime is eventually
printed, but the infinite stream never finishes.  Bounded modes make runs easy
to reproduce and independently verify.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Iterator


def base_primes(limit: int) -> list[int]:
    """Return every prime at most limit using an ordinary Eratosthenes sieve."""
    if limit < 2:
        return []
    flags = bytearray(b"\x01") * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for prime in range(2, math.isqrt(limit) + 1):
        if not flags[prime]:
            continue
        count = (limit - prime * prime) // prime + 1
        flags[prime * prime:limit + 1:prime] = b"\x00" * count
    return [value for value, is_prime in enumerate(flags) if is_prime]


def primes_in_segment(low: int, high: int) -> Iterator[int]:
    """Yield exactly the primes in the closed interval [low, high]."""
    if high < 2 or high < low:
        return
    low = max(low, 2)
    flags = bytearray(b"\x01") * (high - low + 1)
    for prime in base_primes(math.isqrt(high)):
        first = max(prime * prime, ((low + prime - 1) // prime) * prime)
        if first > high:
            continue
        count = (high - first) // prime + 1
        flags[first - low:high - low + 1:prime] = b"\x00" * count
    for offset, is_prime in enumerate(flags):
        if is_prime:
            yield low + offset


def prime_stream(start: int = 2, segment_size: int = 1_000_000) -> Iterator[int]:
    """Yield all primes at least start, in increasing order, without an end."""
    low = max(start, 2)
    while True:
        high = low + segment_size - 1
        yield from primes_in_segment(low, high)
        low = high + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lazy exhaustive prime stream; use --forever explicitly."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--until", type=int, help="stop after this inclusive bound")
    mode.add_argument("--count", type=int, help="emit this many primes")
    mode.add_argument(
        "--forever", action="store_true", help="emit the infinite stream until stopped"
    )
    parser.add_argument("--from", dest="start", type=int, default=2)
    parser.add_argument("--segment-size", type=int, default=1_000_000)
    args = parser.parse_args()
    if args.segment_size < 1:
        parser.error("--segment-size must be positive")
    if args.count is not None and args.count < 0:
        parser.error("--count must be non-negative")
    return args


def main() -> int:
    args = parse_args()
    if args.count == 0 or (args.until is not None and args.until < max(args.start, 2)):
        return 0

    emitted = 0
    batch: list[str] = []
    try:
        for prime in prime_stream(args.start, args.segment_size):
            if args.until is not None and prime > args.until:
                break
            batch.append(str(prime))
            emitted += 1
            if len(batch) >= 8192:
                sys.stdout.write("\n".join(batch) + "\n")
                sys.stdout.flush()
                batch.clear()
            if args.count is not None and emitted >= args.count:
                break
        if batch:
            sys.stdout.write("\n".join(batch) + "\n")
            sys.stdout.flush()
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
