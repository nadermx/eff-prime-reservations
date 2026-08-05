# Full second-candidate P40 pipeline

Captured 2026-08-05 UTC. This is a pre-result operational milestone, not a
prime result or an EFF award claim.

## Outcome

The independently reserved second qualifying candidate

\[
M_{332228213}=2^{332228213}-1
\]

has 100,010,658 decimal digits. Its complete P-1-to-PRP/proof pipeline is now
staged on VM101's Tesla P40 and fault-tested without interrupting the active
`M332228177` P-1 job. The H200 was not used.

The exact PRPLL binary staged for the possible PRP run has SHA-256
`04073474c66c374a7ef91c18b6b3c30a5bd726969b67707a533888812f44c27d`.
The signed exact-exponent reservation has SHA-256
`ba99b88790245719a747b691aec9f32afa8fa0e5be2046575fbf3082e2b22d12`.

## Fail-closed transition table

| Input state | Permitted transition |
|---|---|
| Current `M332228177` P-1 still active or unclassified | Nothing starts |
| Current P-1 has a classified no-factor or independently verified factor receipt | Start the planned `M332228213` P-1 pass after a fresh official status check |
| `M332228213` P-1 exits nonzero, remains active, or lacks an admissible receipt | PRP remains stopped |
| `M332228213` P-1 returns an independently verified factor | Append terminal `result`, write the stopped marker; PRP never starts |
| `M332228213` P-1 returns a zero-exit, exact-bound no-factor receipt | Append nonterminal `checkpoint`, fetch official status again, extend the ledger, pass exact binary/GPU/disk/signature gates, then start PRP |
| A transition marker does not exist | The local evidence synchronizer copies nothing |
| The PRP service/proof directory does not exist | The off-VM proof backup exits successfully without manufacturing evidence |

The PRP launcher requires at least 100,000,000,000 available bytes before its
first run. The staging receipt recorded 116,919,554,048 bytes available. It
also recorded both handoff paths active/waiting, both candidate-2 compute
services inactive/dead, and an actual negative PRP predecessor test returning
exit 64.

## Fault tests

The executable fault-test receipt records:

- shell syntax and systemd unit verification;
- a no-marker synchronizer no-op;
- a pre-launch proof-backup no-op;
- acceptance of a valid remote append-only ledger extension;
- retention of a later valid local ledger;
- rejection of two individually valid but divergent ledger children;
- admission of a fresh status and PRP lane after a no-factor `checkpoint`;
- rejection of any later status/lane after a verified-factor `result`;
- enabled/waiting five-minute evidence-sync and ten-minute proof-backup timers;
- an active predecessor on the selected Tesla P40 and no candidate-2 start.

The compact verifier also binds the staged remote hashes back to the shareable
source files and checks both the verified-factor stop branch and the
completed-no-factor PRP branch.

The retained v1/v2 staging receipts are audit history, not current authority.
V2 removed a receipt-publication race; the subsequent state-machine replay
showed that no-factor must be a nonterminal `checkpoint`, not terminal
`result`. V3 is the first receipt binding both corrections before arithmetic
started.

## Reproduction

From the research root or the released `deliverables` directory, run:

```bash
python3 verify_second_candidate_pipeline.py
```

The expected terminal line is:

```text
PASS M332228213 full P-1/PRP pipeline: P40-only, both negative predecessor gates, append-only evidence sync, and proof backup
```

Evidence hashes at capture:

- full VM101 staging receipt:
  `59e7f71a402cf5b38486c52a49ff21b772a6c51f554245e23c69d439b7a9ff82`;
- pipeline fault-test receipt:
  `8820ef749ef2687fad3e7b1b3f57e531bacfc198aad8a16d287367494686a58c`;
- verifier:
  `2c8eb2c592f6a9183595d2494c9c0b9c9af48ca46c21c1c09e20ae49c385ea3b`.

## Scope boundary

No result exists for `M332228213`. No PRP result, Lucas-Lehmer residue,
deterministic primality proof, refereed publication, or EFF claim is implied.
This milestone removes an operational handoff/evidence gap while the actual
qualifying computations continue.
