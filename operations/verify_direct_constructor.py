#!/usr/bin/env python3
"""Verify the retained direct-prime prototype and a mathematical tamper."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


EXPECTED_CERTIFICATE_SHA256 = (
    "55b1d04fb738b0bcc5c9688c49cd3f5d01afab4938b5f62710c05ad82319486d"
)
EXPECTED_CANDIDATE_SHA256 = (
    "28af2b4f05a4b8a79919a4694397228849c191a49d068aad8e367cb09a459271"
)


def canonical_payload(document: dict[str, object]) -> bytes:
    payload = dict(document)
    payload.pop("certificate_payload_sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    release = script_dir.parent if script_dir.name == "verifiers" else script_dir
    evidence = release / "evidence" / "direct-pocklington-1000d-20260805T0538Z"
    if not evidence.exists() and script_dir.name != "verifiers":
        evidence = release / "runs" / "direct-pocklington-1000d-20260805T0538Z"
    certificate_path = evidence / "certificate.json"
    raw = certificate_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_CERTIFICATE_SHA256
    document = json.loads(raw)

    sys.path.insert(0, str(release / "tools"))
    from verify_direct_digit_pocklington import verify  # noqa: E402

    candidate, steps = verify(document)
    candidate_text = str(candidate)
    assert len(candidate_text) == 1_000
    assert hashlib.sha256(candidate_text.encode()).hexdigest() == (
        EXPECTED_CANDIDATE_SHA256
    )
    assert steps == 10
    final_search = document["nodes"][-1]["search"]
    assert final_search["attempts"] == 1_653
    assert final_search["sieve_rejections"] == 1_464
    assert final_search["fermat_rejections"] == 188
    assert final_search["small_witness_rejections"] == 0

    tampered = copy.deepcopy(document)
    tampered["nodes"][-1]["r"] = str(int(tampered["nodes"][-1]["r"]) + 1)
    tampered["certificate_payload_sha256"] = hashlib.sha256(
        canonical_payload(tampered)
    ).hexdigest()
    try:
        verify(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("mathematically tampered Pocklington chain accepted")

    generator_stdout = (evidence / "generator.stdout").read_text()
    verifier_stdout = (evidence / "verifier.stdout").read_text()
    assert "certified 1000-digit prime in 10 Pocklington steps" in generator_stdout
    assert "PASS 1000-digit prime by 10-step Pocklington chain" in verifier_stdout

    print("PASS distinct 1,000-digit prime and ten-step Pocklington chain")
    print(f"PASS candidate decimal SHA-256: {EXPECTED_CANDIDATE_SHA256}")
    print("PASS independent congruence reconstruction and mathematical tamper rejection")
    print("SCOPE: proof-carrying prototype; selector still searched 1,653 multipliers")


if __name__ == "__main__":
    main()
