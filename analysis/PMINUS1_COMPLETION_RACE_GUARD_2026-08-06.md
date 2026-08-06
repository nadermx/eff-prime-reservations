# P-1 completion race guard — 2026-08-06

## Outcome

The live `M332228177` P-1 terminal classifier is hardened against a real
sub-second ordering race without restarting or signalling the arithmetic.
The resumed launcher writes `exit_status.txt` before it appends the final end
timestamp and GPU telemetry. Because systemd watches that status file, the
old classifier could start before its required provenance existed, fail, and
leave the terminal result unpublished.

The classifier now waits for both the terminal process to disappear and final
metadata whose filesystem timestamp is newer than `exit_status.txt`. It
handles the initial-run and resumed-run layouts separately and fails closed
after 30 seconds.

## Live deployment evidence

- Candidate: `M332228177`
- Worker: VM101 Tesla P40
- GPU UUID: `GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2`
- Arithmetic PID before and after: `69077`
- Arithmetic restarts or signals: none
- H200 used: no
- Old classifier SHA-256: `3ca39854d4e871273950e9516d2f1e21eaa0776576183f1eeb9447962da29fb2`
- Hardened classifier SHA-256: `49fa4833ae467a03fa46ed7a78d2d0521669660681a0852a9fcaf54de7d0f0b9`
- Deployment receipt SHA-256: `82e6ff42e59fb5b55b8561d846e58679fc740e57ae5fbbe70a17f81214250441`
- Fault-test receipt SHA-256: `a42864cd108bfe72f67edbfa681929dbb3f28b5138a36085f477b9550da6ee33`

The live negative gate returned exit 64 while `exit_status.txt` was absent.
The P-1 process retained the same PID, zero restarts, 100% P40 utilization,
and entered the final `857–960 of 960` relative-prime pass afterward.

## Reproduction

From the release root:

```sh
python3 verifiers/verify_pminus1_completion_race_guard.py
```

The verifier checks all receipt-bound hashes, shell syntax, live deployment
scope, and reconstructs both timing orders. It rejects stale resume metadata,
missing final telemetry, and missing initial-run metadata; it accepts only the
two settled terminal layouts.

## Scope

This closes an evidence-publication race. It is not a P-1 classification,
factor, probable-prime result, deterministic primality proof, refereed paper,
or EFF claim.
