#!/usr/bin/env python3
"""Validate one complete PRPLL JSON-lines result for an exact assignment."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


HEX16_RE = re.compile(r"^[0-9a-fA-F]{16}$")
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
HEX512_RE = re.compile(r"^[0-9a-fA-F]{512}$")


def matches_worktype(requested: str, observed: object) -> bool:
    # Current PRPLL writes versioned Fermat results as PRP-3.  Treat the CLI
    # name PRP as the logical test family, but do not silently admit unknown
    # PRP variants with different result semantics.
    return observed == ("PRP-3" if requested == "PRP" else "LL")


def validate_common(result: dict[str, object]) -> None:
    if result.get("status") not in {"P", "C"}:
        raise ValueError(f"invalid terminal status: {result.get('status')!r}")
    residue = result.get("res64")
    if not isinstance(residue, str) or HEX16_RE.fullmatch(residue) is None:
        raise ValueError(f"invalid 64-bit residue field: {residue!r}")
    program = result.get("program")
    if not isinstance(program, dict) or program.get("name") != "prpll":
        raise ValueError("result is not attributed to PRPLL")
    version = program.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("PRPLL version is absent")
    timestamp = result.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        raise ValueError("result timestamp is absent")


def validate_prp3(result: dict[str, object]) -> None:
    if result.get("residue-type") != 1:
        raise ValueError(f"unexpected PRP residue type: {result.get('residue-type')!r}")
    res2048 = result.get("res2048")
    if not isinstance(res2048, str) or HEX512_RE.fullmatch(res2048) is None:
        raise ValueError("invalid PRP res2048 field")
    errors = result.get("errors")
    if not isinstance(errors, dict) or errors.get("gerbicz") != 0:
        raise ValueError(f"PRP Gerbicz error count is not zero: {errors!r}")
    proof = result.get("proof")
    if not isinstance(proof, dict):
        raise ValueError("PRP proof metadata is absent")
    if proof.get("version") != 1 or proof.get("hashsize") != 64:
        raise ValueError(f"unexpected PRP proof format: {proof!r}")
    power = proof.get("power")
    if not isinstance(power, int) or not 4 <= power <= 13:
        raise ValueError(f"invalid PRP proof power: {power!r}")
    md5 = proof.get("md5")
    if not isinstance(md5, str) or HEX32_RE.fullmatch(md5) is None:
        raise ValueError(f"invalid PRP proof MD5: {md5!r}")


def validate_ll(result: dict[str, object]) -> None:
    if result.get("error-code") != "00000000":
        raise ValueError(f"nonzero PRPLL error code: {result.get('error-code')!r}")
    # PRPLL's status P is a claim that the complete Lucas--Lehmer residue is
    # zero.  Independently enforce its necessary Res64 consequence so a
    # malformed or tampered P record cannot trigger a primality claim.
    if result.get("status") == "P" and result.get("res64") != "0000000000000000":
        raise ValueError("LL prime status has a nonzero residue")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_file", type=Path)
    parser.add_argument("--exponent", type=int, required=True)
    parser.add_argument("--worktype", choices=("PRP", "LL"), required=True)
    args = parser.parse_args()

    if not args.result_file.is_file():
        raise ValueError(f"result file is absent: {args.result_file}")

    matches: list[dict[str, object]] = []
    for line_number, line in enumerate(
        args.result_file.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON on line {line_number}: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number} is not a JSON object")
        if (
            record.get("exponent") == args.exponent
            and matches_worktype(args.worktype, record.get("worktype"))
        ):
            matches.append(record)

    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one M{args.exponent} {args.worktype} result; "
            f"found {len(matches)}"
        )
    result = matches[0]
    validate_common(result)
    if args.worktype == "PRP":
        validate_prp3(result)
    else:
        validate_ll(result)
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
