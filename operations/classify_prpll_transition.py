#!/usr/bin/env python3
"""Bind a validated PRP-3 result to its complete PRPLL proof file."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


HEX16_RE = re.compile(r"^[0-9a-fA-F]{16}$")
HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
HEX512_RE = re.compile(r"^[0-9a-fA-F]{512}$")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def md5(path: Path) -> str:
    # MD5 is part of the upstream proof metadata format; SHA-256 is retained
    # separately for artifact integrity.
    value = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("validated_result", type=Path)
    parser.add_argument("proof_file", type=Path)
    parser.add_argument("--expected-exponent", type=int, required=True)
    parser.add_argument("--expected-proof-power", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    require(args.expected_exponent > 2 and args.expected_exponent % 2 == 1, "invalid exponent")
    require(4 <= args.expected_proof_power <= 13, "invalid expected proof power")
    require(args.validated_result.is_file(), "validated result is absent")
    require(args.proof_file.is_file(), "proof file is absent")
    require(not args.output.exists(), "refusing to overwrite transition receipt")

    result = json.loads(args.validated_result.read_text(encoding="utf-8"))
    require(isinstance(result, dict), "validated result is not an object")
    require(result.get("exponent") == args.expected_exponent, "result exponent mismatch")
    require(result.get("worktype") == "PRP-3", "result is not PRP-3")
    require(result.get("status") in {"P", "C"}, "result status is not terminal")
    require(result.get("residue-type") == 1, "unexpected residue type")
    require(isinstance(result.get("res64"), str) and HEX16_RE.fullmatch(result["res64"]), "invalid res64")
    require(isinstance(result.get("res2048"), str) and HEX512_RE.fullmatch(result["res2048"]), "invalid res2048")
    require(result.get("errors") == {"gerbicz": 0}, "nonzero or malformed Gerbicz errors")
    require(isinstance(result.get("program"), dict) and result["program"].get("name") == "prpll", "wrong program")

    proof = result.get("proof")
    require(isinstance(proof, dict), "proof metadata is absent")
    require(proof.get("version") == 1, "unexpected proof metadata version")
    require(proof.get("hashsize") == 64, "unexpected proof hash size")
    require(proof.get("power") == args.expected_proof_power, "proof power mismatch")
    require(isinstance(proof.get("md5"), str) and HEX32_RE.fullmatch(proof["md5"]), "invalid proof MD5")

    expected_name = f"{args.expected_exponent}-{args.expected_proof_power}.proof"
    require(args.proof_file.name == expected_name, "proof filename mismatch")
    expected_header = (
        "PRP PROOF\n"
        "VERSION=2\n"
        "HASHSIZE=64\n"
        f"POWER={args.expected_proof_power}\n"
        f"NUMBER=M{args.expected_exponent}\n"
    ).encode("ascii")
    with args.proof_file.open("rb") as stream:
        observed_header = stream.read(len(expected_header))
    require(observed_header == expected_header, "proof header mismatch")
    residue_bytes = (args.expected_exponent - 1) // 8 + 1
    expected_size = len(expected_header) + (args.expected_proof_power + 1) * residue_bytes
    require(args.proof_file.stat().st_size == expected_size, "proof size mismatch")
    observed_md5 = md5(args.proof_file)
    require(observed_md5.lower() == proof["md5"].lower(), "proof MD5 does not match result")

    classification = (
        "probable_prime_trigger" if result["status"] == "P"
        else "verified_composite_prp"
    )
    receipt = {
        "schema": "eff.prpll-prp-to-ll-transition.v1",
        "captured_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exponent": args.expected_exponent,
        "classification": classification,
        "prp_status": result["status"],
        "prp_res64": result["res64"].lower(),
        "prp_res2048": result["res2048"].lower(),
        "prp_program_version": result["program"]["version"],
        "validated_result_sha256": sha256(args.validated_result),
        "proof": {
            "path_basename": args.proof_file.name,
            "power": args.expected_proof_power,
            "size_bytes": expected_size,
            "md5_from_result": proof["md5"].lower(),
            "md5_recomputed": observed_md5.lower(),
            "sha256": sha256(args.proof_file),
            "execution_verification_completed": False,
        },
        "deterministic_lucas_lehmer_required": result["status"] == "P",
        "scope": (
            "A probable-prime trigger starts deterministic Lucas-Lehmer and distinct "
            "Mlucas confirmation; it is not a primality proof or EFF claim."
            if result["status"] == "P" else
            "A proof-bound PRP composite result terminates this candidate; it is not a prime claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        raise SystemExit(1)
