#!/usr/bin/env python3
"""Cross-check a large bounded prefix from the lazy all-primes stream."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BOUND = 1_000_000
EXPECTED_COUNT = 78_498
EXPECTED_LAST = 999_983


def independent_dense_sieve(limit: int) -> list[int]:
    flags = bytearray(b"\x01") * (limit + 1)
    flags[0:2] = b"\x00\x00"
    candidate = 2
    while candidate * candidate <= limit:
        if flags[candidate]:
            multiple = candidate * candidate
            while multiple <= limit:
                flags[multiple] = 0
                multiple += candidate
        candidate += 1
    return [value for value in range(2, limit + 1) if flags[value]]


def is_complete_prefix(values: list[int], limit: int) -> bool:
    return values == independent_dense_sieve(limit)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    release = script_dir.parent if script_dir.name == "verifiers" else script_dir
    generator = release / "tools" / "prime_stream.py"
    result = subprocess.run(
        [
            sys.executable, str(generator), "--until", str(BOUND),
            "--segment-size", "32768",
        ],
        capture_output=True, check=False, text=True,
    )
    assert result.returncode == 0, result.stderr
    values = [int(line) for line in result.stdout.splitlines()]
    assert len(values) == EXPECTED_COUNT
    assert values[-1] == EXPECTED_LAST
    assert is_complete_prefix(values, BOUND)

    tampered = values.copy()
    del tampered[len(tampered) // 2]
    assert not is_complete_prefix(tampered, BOUND)

    print(f"PASS exhaustive prime prefix through {BOUND:,}: {len(values):,} primes")
    print(f"PASS final prime: {values[-1]:,}")
    print("PASS independently reconstructed dense sieve and tamper rejection")
    print("SCOPE: lazy enumeration; no finite run emits the infinite prime set")


if __name__ == "__main__":
    main()
