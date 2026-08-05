# Third qualifying candidate reserved

Captured 2026-08-05 UTC. This is a non-duplication and continuity milestone,
not a primality result or EFF award claim.

## Outcome

The exact backup candidate

\[
M_{332228447}=2^{332228447}-1
\]

has 100,010,728 decimal digits. A fresh official snapshot fetched at
`2026-08-05T23:14:43Z` reported no assignment, no known factor, and no
published result. The signed reservation expires at
`2027-01-31T23:16:08Z` and was publicly anchored by commit
`ab2affa16a5859537990f681030dc8849d228eb1`.

No arithmetic has started for this exponent. Its start gate requires an idle
P40 after the earlier reserved lanes, a new official-status fetch, and a new
measured allocation decision.

## Retained planning result

The same measured factor-first model used for the earlier lanes selected
`B1=1,495,000` and `B2=32,142,500`. It estimates 23.5139007 P40-hours,
a 2.4527799% conditional chance of finding a factor after the historical
P-1 pass failed, 27.5419714 expected PRP-hours saved, and 4.0280707 net
expected P40-hours saved. These are explicitly heuristic planning values;
a no-factor P-1 result would not be evidence of primality.

## Single-writer continuity

The reservation added a `status_snapshot` followed by a `reservation` record
to the canonical append-only ledger. That 22-record ledger has SHA-256
`b195433ef1f70feaf999eba656fc2151bb4b866abaab5ff1ff76d04bdc056b9c`.
Before the active predecessor could finish, the exact ledger bytes were
installed into the inactive VM101 candidate-2 staging directory. The v5
receipt records:

- active `M332228177` P-1 on Tesla P40;
- inactive `M332228213` P-1 and PRP services;
- no start markers for either queued candidate-2 lane;
- the same staged ledger digest as the local canonical ledger;
- no H200 use.

This preserves VM101 as the sole future writer of the predecessor
classification and candidate-2 start records while ensuring the backup
reservation precedes those transitions in the one canonical chain.

## Replay

From the research root or shareable `deliverables` directory:

```bash
python3 verify_third_candidate_reservation.py
```

The verifier checks the detached signature, official-snapshot manifest,
100,010,728-digit calculation, selected P-1 model and warning, public commit
binding, append-only ledger history, absence of a work-start record, P40
identity, inactive queued services, and v5 staged-ledger hash.

Key SHA-256 values:

- reservation: `6e7f7340f1c30edde0641a95d9825c5ac943d66ac228e68c389039e87b86b341`;
- preflight: `76eafca76d4d13098d0b67f10757820360607fdbfd0ff98c0300eada7a108411`;
- P-1 model: `998b9fe344ee2b2300211b19da5cc77fb4513f77944c7fbbc3997a46a7cb005d`;
- v5 staging receipt: `f3a30af6c7d0e4e685571811930f668e0d0aab0e4dad04fb1103ade97c173aa2`;
- verifier: `88d43ac739100b4c6eb6ff73f5f960c6d9585f7ac524f3852d3fbb6302990123`.

## Scope boundary

This reservation reduces a future idle-gap and duplication risk. It does not
identify a prime, prove primality, satisfy independent verification, provide
a refereed discovery publication, or support an EFF claim.
