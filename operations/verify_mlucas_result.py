#!/usr/bin/env python3
"""Validate one exact, terminal Mlucas Lucas--Lehmer result record."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


HEX16_RE = re.compile(r"^[0-9a-fA-F]{16}$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_file", type=Path)
    parser.add_argument("--exponent", type=int, required=True)
    args = parser.parse_args()
    if not args.result_file.is_file():
        raise ValueError(f"result file is absent: {args.result_file}")

    matches: list[dict[str, object]] = []
    for line_number, line in enumerate(
        args.result_file.read_text(encoding="utf-8", errors="strict").splitlines(), 1
    ):
        start = line.find("{")
        if start < 0:
            continue
        try:
            record = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("exponent") == args.exponent and record.get("worktype") == "LL":
            matches.append(record)
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one M{args.exponent} Mlucas LL result; found {len(matches)}"
        )

    result = matches[0]
    if result.get("status") not in {"P", "C"}:
        raise ValueError(f"invalid terminal status: {result.get('status')!r}")
    if result.get("error-code") != "00000000":
        raise ValueError(f"nonzero Mlucas error code: {result.get('error-code')!r}")
    residue = result.get("res64")
    if not isinstance(residue, str) or HEX16_RE.fullmatch(residue) is None:
        raise ValueError(f"invalid Mlucas residue: {residue!r}")
    if result["status"] == "P" and residue.upper() != "0000000000000000":
        raise ValueError("Mlucas prime status has a nonzero LL residue")
    program = result.get("program")
    if not isinstance(program, dict) or program.get("name") != "Mlucas":
        raise ValueError("result is not attributed to Mlucas")
    if not isinstance(program.get("version"), str) or not program["version"]:
        raise ValueError("Mlucas version is absent")
    errors = result.get("errors")
    if errors is not None:
        if not isinstance(errors, dict) or any(value != 0 for value in errors.values()):
            raise ValueError(f"Mlucas result reports errors: {errors!r}")

    json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
