#!/usr/bin/env python3
"""Validate one complete PRPLL JSON-lines result for an exact assignment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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
            and record.get("worktype") == args.worktype
        ):
            matches.append(record)

    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one M{args.exponent} {args.worktype} result; "
            f"found {len(matches)}"
        )
    result = matches[0]
    if result.get("status") not in {"P", "C"}:
        raise ValueError(f"invalid terminal status: {result.get('status')!r}")
    if result.get("error-code") != "00000000":
        raise ValueError(f"nonzero PRPLL error code: {result.get('error-code')!r}")
    residue = result.get("res64")
    if not isinstance(residue, str) or len(residue) != 16:
        raise ValueError(f"invalid 64-bit residue field: {residue!r}")
    int(residue, 16)
    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
