#!/usr/bin/env python3
"""Classify a completed CUDAPm1 log and emit a deterministic receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


FACTOR_SCHEMA = "eff.mersenne-factor-certificate.v1"
RECEIPT_SCHEMA = "eff.cudapm1-completion-receipt.v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--exponent", type=int, required=True)
    parser.add_argument("--b1", type=int, required=True)
    parser.add_argument("--b2", type=int, required=True)
    parser.add_argument("--exit-status", type=int, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--factor-certificate", type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error(f"refusing to overwrite {args.receipt}")
    if args.factor_certificate and args.factor_certificate.exists():
        parser.error(f"refusing to overwrite {args.factor_certificate}")

    log = args.log.read_text(encoding="utf-8", errors="replace")
    factor_pattern = re.compile(
        rf"^M{args.exponent} has a factor: ([0-9]+) \(P-1, .+$",
        re.MULTILINE,
    )
    factors = factor_pattern.findall(log)
    if len(set(factors)) > 1:
        raise SystemExit("multiple distinct exact-exponent factors in log")

    classification: str
    matched_line: str | None = None
    certificate_sha256: str | None = None
    factor_value: str | None = None
    if factors:
        q = int(factors[-1])
        if q <= 1 or q.bit_length() >= args.exponent:
            raise SystemExit("reported factor is not a proven proper-size divisor")
        if pow(2, args.exponent, q) != 1:
            raise SystemExit("reported factor fails 2**p mod q == 1")
        k, remainder = divmod(q - 1, 2 * args.exponent)
        certificate: dict[str, object] = {
            "schema": FACTOR_SCHEMA,
            "exponent": args.exponent,
            "factor": str(q),
            "pow2_residue": 1,
            "source": str(args.log),
        }
        if remainder == 0 and k >= 1:
            certificate["k"] = str(k)
        if args.factor_certificate is None:
            raise SystemExit("verified factor requires --factor-certificate")
        write_new(args.factor_certificate, certificate)
        certificate_sha256 = sha256(args.factor_certificate)
        classification = "verified_factor"
        factor_value = str(q)
        matched_line = next(
            line for line in log.splitlines()
            if line.startswith(f"M{args.exponent} has a factor: {q} ")
        )
    elif args.exit_status != 0:
        classification = "execution_failure"
    else:
        terminal_patterns = [
            rf"^M{args.exponent} Stage 2 found no factor \(P-1, .+$",
        ]
        if args.b2 <= args.b1:
            terminal_patterns.append(
                rf"^M{args.exponent} Stage 1 found no factor \(P-1, .+$"
            )
        terminal_lines = [
            line for line in log.splitlines()
            if any(re.match(pattern, line) for pattern in terminal_patterns)
        ]
        if terminal_lines:
            classification = "completed_no_factor_report"
            matched_line = terminal_lines[-1]
        else:
            classification = "zero_exit_without_terminal_result"

    receipt: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "classified_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exponent": args.exponent,
        "b1": args.b1,
        "b2": args.b2,
        "program_exit_status": args.exit_status,
        "log": str(args.log),
        "log_sha256": sha256(args.log),
        "classification": classification,
        "matched_terminal_line": matched_line,
        "factor": factor_value,
        "factor_certificate_sha256": certificate_sha256,
        "scope": "local program-result classification; no-factor reports require audit, while a verified factor is independently definitive",
    }
    write_new(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
