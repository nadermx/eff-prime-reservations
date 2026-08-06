# P-1 completion race guard — 2026-08-06

## Outcome

The live `M332228177` P-1 terminal classifier is hardened against a real
sub-second ordering race without restarting or signalling the arithmetic.
The resumed launcher writes `exit_status.txt` before it appends the final end
timestamp and GPU telemetry. Because systemd watches that status file, the
old classifier could start before its required provenance existed, fail, and
leave the terminal result unpublished.

The classifier now waits for the terminal process and both exact P-1 systemd
services to become inactive, plus final metadata whose filesystem timestamp
is newer than `exit_status.txt`. It handles the initial-run and resumed-run
layouts separately and fails closed after 30 seconds.

## Live deployment evidence

- Candidate: `M332228177`
- Worker: VM101 Tesla P40
- GPU UUID: `GPU-854d60af-1b7f-b0e5-5b68-b9073f6f7dc2`
- Arithmetic PID before and after: `69077`
- Arithmetic restarts or signals: none
- H200 used: no
- Old classifier SHA-256: `3ca39854d4e871273950e9516d2f1e21eaa0776576183f1eeb9447962da29fb2`
- First hardened classifier SHA-256: `49fa4833ae467a03fa46ed7a78d2d0521669660681a0852a9fcaf54de7d0f0b9`
- Final service-aware classifier SHA-256: `5ff4c0ed8954a0a61083933f244437131c70f331d865ecba0f1b2ec3d6a53912`
- Deployment receipt SHA-256: `82e6ff42e59fb5b55b8561d846e58679fc740e57ae5fbbe70a17f81214250441`
- Service-aware v2 receipt SHA-256: `01078b2f6a1073c2fadb1c051a0668ca7b1c786f374e4e92a3c35760649ed3df`
- Fault-test receipt SHA-256: `9d23e1745331595eb38f861edf0154ec0df66d512a26dd1b2c6ee549044cfdb8`
- Public replay commit: `19f42805c47f0ae062724084114dfe089a6ec676`

The live negative gate returned exit 64 while `exit_status.txt` was absent.
The P-1 process retained the same PID, zero restarts, 100% P40 utilization,
and entered the final `857–960 of 960` relative-prime pass afterward.

The same terminal invariant was then deployed before arithmetic to both
queued branches:

- `M332228213` VM101 classifier SHA-256: `11f4423283537abf9bd20955f32cdaceb2f15b64706d88802e3675ad1ee2256b`
- `M332228447` VM102 classifier SHA-256: `805bf07e09c3f916d6067ee6f375927a28f9d72929401c8b35b58a9d9702874a`
- Queued-branch deployment receipt SHA-256: `2bfc8c8baf35b16365869c56df7d116ebc500d650b65c9ac276edc67f2d316cc`

Both queued arithmetic pairs remained inactive. Candidate 1 retained the same
P-1 and PRP owner PIDs on the two P40s, and both preterminal classifier calls
failed closed at the absent exit marker.

## Reproduction

From the release root:

```sh
python3 verifiers/verify_pminus1_completion_race_guard.py
```

The verifier checks all receipt-bound hashes, shell syntax, live deployment
scope, both service-aware deployments, and reconstructs both timing orders.
It rejects stale resume metadata, missing final telemetry, and missing
initial-run metadata; it accepts only settled terminal layouts.

## Scope

This closes an evidence-publication race. It is not a P-1 classification,
factor, probable-prime result, deterministic primality proof, refereed paper,
or EFF claim.
