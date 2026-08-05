#!/usr/bin/env python3
"""Independently verify a recursive direct-digit Pocklington certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


SCHEMA = "eff.direct-pocklington-chain.v1"

if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


def decimal_integer(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} is boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError(f"{name} is not a decimal integer")


def trial_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    divisor = 3
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 2
    return True


def verify(document: dict[str, object]) -> tuple[int, int]:
    if document.get("schema") != SCHEMA:
        raise ValueError("wrong schema")
    payload = dict(document)
    claimed_hash = payload.pop("certificate_payload_sha256", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if claimed_hash != hashlib.sha256(canonical).hexdigest():
        raise ValueError("certificate payload hash mismatch")

    nodes = document.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("empty node chain")
    seed = nodes[0]
    if not isinstance(seed, dict):
        raise ValueError("invalid seed node")
    previous = decimal_integer(seed.get("prime"), "seed prime")
    if not trial_prime(previous):
        raise ValueError("seed is not prime by trial division")

    for expected_index, raw_node in enumerate(nodes[1:], start=1):
        if not isinstance(raw_node, dict):
            raise ValueError("invalid chain node")
        if raw_node.get("index") != expected_index:
            raise ValueError("nonconsecutive node index")
        n = decimal_integer(raw_node.get("prime"), "prime")
        q = decimal_integer(raw_node.get("q"), "q")
        r = decimal_integer(raw_node.get("r"), "r")
        a = decimal_integer(raw_node.get("witness"), "witness")
        if q != previous:
            raise ValueError("node does not use preceding certified prime")
        if n != 2 * r * q + 1:
            raise ValueError("node equation N=2*r*q+1 fails")
        if q * q <= n:
            raise ValueError("known prime factor does not exceed sqrt(N)")
        if pow(a, n - 1, n) != 1:
            raise ValueError("Fermat congruence fails")
        if math.gcd(pow(a, 2 * r, n) - 1, n) != 1:
            raise ValueError("Pocklington gcd condition fails")
        if int(raw_node.get("decimal_digits", -1)) != len(str(n)):
            raise ValueError("node decimal digit count fails")
        previous = n

    candidate = decimal_integer(document.get("candidate"), "candidate")
    if candidate != previous:
        raise ValueError("candidate is not final certified node")
    digits = len(str(candidate))
    if digits != decimal_integer(
        document.get("requested_decimal_digits"), "requested digits"
    ):
        raise ValueError("candidate does not have requested decimal digits")
    if digits != decimal_integer(
        document.get("candidate_decimal_digits"), "candidate digits"
    ):
        raise ValueError("candidate digit field mismatch")
    return candidate, len(nodes) - 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args()
    document = json.loads(args.certificate.read_text())
    if not isinstance(document, dict):
        raise SystemExit("FAIL: certificate root is not an object")
    try:
        candidate, steps = verify(document)
    except ValueError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    print(f"PASS {len(str(candidate))}-digit prime by {steps}-step Pocklington chain")
    print(f"candidate_sha256={hashlib.sha256(str(candidate).encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
