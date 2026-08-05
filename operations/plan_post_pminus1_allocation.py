#!/usr/bin/env python3
"""Compare measured post-P-1 uses of one Tesla P40.

The timing arithmetic is exact given its inputs. Factor probabilities are
explicitly heuristic and are used only to choose between pre-PRP screens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SECONDS_PER_DAY = 86_400.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-exponent", type=int, required=True)
    parser.add_argument("--current-iteration", type=int, required=True)
    parser.add_argument("--second-exponent", type=int, required=True)
    parser.add_argument("--p40-prp-us", type=float, required=True)
    parser.add_argument("--tf-lower-bit", type=int, required=True)
    parser.add_argument("--tf-seconds", type=float, required=True)
    parser.add_argument("--pminus1-analysis", type=Path, required=True)
    parser.add_argument("--pminus1-strategy", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not 0 <= args.current_iteration < args.current_exponent:
        parser.error("current iteration must be within the current exponent")
    if args.second_exponent < 2 or args.p40_prp_us <= 0:
        parser.error("second exponent and timing must be positive")
    if args.tf_lower_bit < 2 or args.tf_seconds <= 0:
        parser.error("TF depth and timing must be positive")

    p1 = json.loads(args.pminus1_analysis.read_text(encoding="utf-8"))
    if p1["exponent"] != args.second_exponent:
        parser.error("P-1 analysis exponent does not match second candidate")
    strategy = p1["strategies"][args.pminus1_strategy]
    p1_probability = strategy["autoprimenet_probability"][
        "incremental_conditional_after_old_pass_failed"
    ]
    p1_seconds = strategy["runtime_model"]["total_p40_hours"] * 3600.0

    seconds_per_iteration = args.p40_prp_us / 1_000_000.0
    current_remaining_seconds = (
        args.current_exponent - args.current_iteration
    ) * seconds_per_iteration
    second_prp_seconds = args.second_exponent * seconds_per_iteration

    tf_probability = 1.0 / args.tf_lower_bit
    # A factor, if present in the band, is modeled uniformly over its measured
    # runtime. The current PRP proceeds concurrently on another P40.
    tf_remaining_at_expected_hit = max(
        0.0, current_remaining_seconds - args.tf_seconds / 2.0
    )
    tf_expected_saved = tf_probability * tf_remaining_at_expected_hit
    tf_net = tf_expected_saved - args.tf_seconds

    p1_expected_saved = p1_probability * second_prp_seconds
    p1_net = p1_expected_saved - p1_seconds

    output = {
        "schema": "eff.post-pminus1-allocation.v1",
        "warning": (
            "Timings derive from measurements; all factor probabilities are "
            "heuristic and no screen is evidence of primality."
        ),
        "inputs": {
            "current_exponent": args.current_exponent,
            "current_iteration": args.current_iteration,
            "second_exponent": args.second_exponent,
            "p40_prp_us_per_iteration": args.p40_prp_us,
            "tf_lower_bit": args.tf_lower_bit,
            "tf_measured_seconds": args.tf_seconds,
            "pminus1_analysis": str(args.pminus1_analysis),
            "pminus1_strategy": args.pminus1_strategy,
        },
        "current_prp": {
            "remaining_iterations": args.current_exponent - args.current_iteration,
            "remaining_days": current_remaining_seconds / SECONDS_PER_DAY,
        },
        "second_candidate_cold_prp": {
            "modeled_days": second_prp_seconds / SECONDS_PER_DAY,
        },
        "current_candidate_tf": {
            "heuristic_factor_probability": tf_probability,
            "p40_cost_hours": args.tf_seconds / 3600.0,
            "expected_current_prp_hours_saved": tf_expected_saved / 3600.0,
            "net_expected_p40_hours_saved": tf_net / 3600.0,
            "modeled_cost_effective": tf_net > 0,
        },
        "second_candidate_pminus1": {
            "b1": strategy["b1"],
            "b2": strategy["b2"],
            "heuristic_conditional_factor_probability": p1_probability,
            "p40_cost_hours": p1_seconds / 3600.0,
            "expected_second_prp_hours_saved": p1_expected_saved / 3600.0,
            "net_expected_p40_hours_saved": p1_net / 3600.0,
            "modeled_cost_effective": p1_net > 0,
        },
        "decision": (
            "second_candidate_deeper_pminus1_then_prp"
            if p1_net > max(0.0, tf_net)
            else "no_modeled_positive_screen"
        ),
        "proof_policy": (
            "PRP remains a composite screen; a P result requires a separate "
            "deterministic Lucas-Lehmer run and independent verification."
        ),
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(rendered.encode("utf-8"))
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
