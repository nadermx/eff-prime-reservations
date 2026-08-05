#!/usr/bin/env python3
"""Construct a deterministic D-digit prime with a recursive Pocklington proof.

This is an equation-first prototype.  Starting from the certified seed 101, it
repeatedly searches the canonical sequence

    N = 2*r*q + 1,

where q is the preceding proved prime and N < q**2.  The latter inequality
makes q > sqrt(N), so one successful Pocklington witness proves N prime.
Correctness is unconditional.  Finding a witness-bearing candidate quickly is
an observed property of a run, not a theorem about every requested size.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "eff.direct-pocklington-chain.v1"
SEED = 101
WITNESS_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43)

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


def small_primes(limit: int) -> list[int]:
    if limit < 2:
        return []
    flags = bytearray(b"\x01") * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for p in range(2, math.isqrt(limit) + 1):
        if flags[p]:
            count = (limit - p * p) // p + 1
            flags[p * p:limit + 1:p] = b"\x00" * count
    return [p for p, value in enumerate(flags) if value]


def decimal_digits(value: int) -> int:
    return len(str(value))


def pocklington_witness(n: int, q: int, r: int) -> tuple[int | None, str]:
    """Return a proof witness or a deterministic rejection category."""
    for base in WITNESS_BASES:
        if base >= n:
            break
        if pow(base, n - 1, n) != 1:
            return None, "fermat_composite"
        if math.gcd(pow(base, 2 * r, n) - 1, n) == 1:
            return base, "proved"
    return None, "no_small_witness"


def construct(digits: int, sieve_bound: int) -> dict[str, object]:
    if digits < 3:
        raise ValueError("the direct chain currently starts from the 3-digit seed 101")
    sieve = [p for p in small_primes(sieve_bound) if p not in (2, SEED)]
    q = SEED
    nodes: list[dict[str, object]] = [
        {
            "index": 0,
            "prime": str(q),
            "decimal_digits": 3,
            "method": "trial_division_seed",
        }
    ]

    while decimal_digits(q) < digits:
        previous_digits = decimal_digits(q)
        # A d-digit q satisfies q**2 >= 10**(2d-2), so targeting at most
        # 2d-2 digits leaves a full decimal decade below q**2 instead of a
        # narrow, potentially empty fringe immediately below q**2.
        target_digits = min(digits, 2 * previous_digits - 2)
        low = 10 ** (target_digits - 1)
        high = min(10 ** target_digits - 1, q * q - 1)
        if high < low:
            raise RuntimeError("recursive interval collapsed before requested size")

        denominator = 2 * q
        r_low = (low - 1 + denominator - 1) // denominator
        r_high = (high - 1) // denominator
        attempts = 0
        sieve_rejections = 0
        fermat_rejections = 0
        witness_rejections = 0
        started = time.monotonic()
        found: tuple[int, int, int] | None = None

        for r in range(r_low, r_high + 1):
            attempts += 1
            n = denominator * r + 1
            if any(n != p and n % p == 0 for p in sieve):
                sieve_rejections += 1
                continue
            witness, category = pocklington_witness(n, q, r)
            if witness is None:
                if category == "fermat_composite":
                    fermat_rejections += 1
                else:
                    witness_rejections += 1
                continue
            found = (n, r, witness)
            break

        if found is None:
            raise RuntimeError(
                f"no Pocklington-certified candidate in deterministic interval "
                f"for {target_digits} digits"
            )
        n, r, witness = found
        elapsed = time.monotonic() - started
        nodes.append(
            {
                "index": len(nodes),
                "prime": str(n),
                "decimal_digits": decimal_digits(n),
                "method": "pocklington_single_known_factor",
                "equation": "N=2*r*q+1",
                "q": str(q),
                "r": str(r),
                "witness": str(witness),
                "q_squared_exceeds_n": q * q > n,
                "fermat_residue": 1,
                "pocklington_gcd": 1,
                "search": {
                    "r_low": str(r_low),
                    "r_high": str(r_high),
                    "attempts": attempts,
                    "sieve_rejections": sieve_rejections,
                    "fermat_rejections": fermat_rejections,
                    "small_witness_rejections": witness_rejections,
                    "elapsed_seconds": elapsed,
                },
            }
        )
        q = n

    payload: dict[str, object] = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requested_decimal_digits": digits,
        "constructor": "deterministic recursive square-root Pocklington chain",
        "candidate": str(q),
        "candidate_decimal_digits": decimal_digits(q),
        "nodes": nodes,
        "scope": (
            "unconditional proof for this output; observed search completion is not "
            "a universal no-search prime formula"
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["certificate_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--digits", type=int, required=True)
    parser.add_argument("--sieve-bound", type=int, default=10_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.sieve_bound < 2:
        parser.error("--sieve-bound must be at least 2")
    if args.output.exists():
        parser.error(f"refusing to overwrite {args.output}")
    try:
        certificate = construct(args.digits, args.sieve_bound)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"PASS constructed and certified {certificate['candidate_decimal_digits']}-digit "
        f"prime in {len(certificate['nodes']) - 1} Pocklington steps"
    )
    print(f"certificate={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
