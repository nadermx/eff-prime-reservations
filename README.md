# Independent Mersenne reservation

This repository publicly reserves exactly `M332228177 = 2^332228177-1` for an
independent search by Johnathan Nader (`@nadermx`).  It reserves no surrounding
range.  A signed extension published after the slow P40 path was measured now
expires at `2027-01-15T04:06:06Z` unless a result or later bounded extension is
published first.

The reservation was prepared only after a fresh official status fetch reported
no known factor, no primality result, and no assignment record.  The complete
raw snapshot, local hash-chain ledger, fixed factor-first plan, signer public
key, detached SSH signature, and SHA-256 manifest are included.  Further fresh
status gates were recorded immediately before each independent compute lane.

Current public progress:

- fixed-bound P-1 began on VM101 at `2026-08-05T04:13:25Z`;
- a second Tesla P40 reproduced the independent 10,000-iteration PRP residue;
- the fresh VM102 PRP gate at `2026-08-05T04:50:04Z` remained unassigned with
  no known factor;
- full checkpointed PRP began at `2026-08-05T04:50:53Z`;
- its iteration-2,000 checkpoint was copied off-VM and SHA-256 verified.

These are active search records, not a probable-prime result, deterministic
Lucas-Lehmer proof, discovery announcement, or award claim.

This is a non-duplication notice, not a claim of primality, discovery,
coordinator assignment, award eligibility, or ownership of the integer.  The
search is independent and does not submit work to PrimeNet.

Verify the detached signature from the repository root:

```sh
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation \
  -s reservation/M332228177.json.sig \
  < reservation/M332228177.json
ssh-keygen -Y verify \
  -f reservation/allowed_signers \
  -I nadermx \
  -n eff-prime-reservation-extension \
  -s reservation/M332228177-extension-20260805.json.sig \
  < reservation/M332228177-extension-20260805.json
sha256sum -c MANIFEST.sha256
```

The exact scope and safety gates are machine-readable in
`reservation/M332228177.json`.
