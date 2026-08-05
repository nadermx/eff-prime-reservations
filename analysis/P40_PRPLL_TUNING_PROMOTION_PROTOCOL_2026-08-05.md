# P40 PRPLL tuning and promotion protocol

## Objective

The live VM102 PRP selected PRPLL's fallback `8M 4:1K:16:256:101` transform
because no P40 `tune.txt` entry covered exponent 332,228,177.  At approximately
12,220 microseconds per iteration, even a modest validated improvement could
save days.  Tuning must not contend with or interrupt either candidate lane.

## Resource gate

The experiment runs only on VM101 after its candidate P-1 service and process
have both ended.  The guarded script refuses execution unless:

- VM101 presents its exact P40 UUID;
- the official PRPLL OpenCL binary hash matches;
- at least 90 GB is free;
- CUDAPm1 is absent;
- a locally captured VM102 receipt is at most ten minutes old, reports the
  exact second P40 UUID, and reports its PRP service active.

The receipt is captured over strict-host-key SSH by
`tools/capture_vm102_prp_health.py` and copied to VM101 by the orchestrator.
The tuning script itself has no credential and no command that stops, restarts,
reconfigures, or writes to VM102.  It is staged only after P-1 ends and its
result is preserved.

## Bounded tune

The official `-tune` interface is restricted to in-place integer NTTs for
exponents from 300,000,000 through 360,000,000, with FP32 excluded and
`NO_ASM` retained for Pascal OpenCL compatibility.  The exact tuning options
are:

```text
noconfig,inplace,ntt,nofp32,minexp=300000000,maxexp=360000000,quick=5
```

This first pass selects transform entries only.  It does not accept speculative
kernel settings or change production.

## Correctness and speed gate

After tuning, the same VM runs two independent 10,000-iteration partial PRPs
on known-composite `M332192831`:

1. the untuned fallback path;
2. the generated `tune.txt` path.

Both must exit zero and reproduce exact residue `bff6cc96e2010c5c`.  A parser
rejects missing, duplicated, malformed, or mismatched final samples.  The
tuned path advances to review only if its sampled iteration time is at least
3% lower than the same-session baseline.

`PROMOTION_REVIEW` is not automatic promotion.  It authorizes a second,
longer benchmark and checkpoint-resume compatibility test.  Only a repeated
speedup, exact residues, zero arithmetic errors, sufficient transform
headroom, and a fresh off-VM production checkpoint can justify a controlled
VM102 restart.  Otherwise the fallback computation continues unchanged.

## Provenance

The runner retains UTC times, GPU telemetry, binary/script hashes, tuner output,
both logs, `/usr/bin/time` records, generated configurations, and a
machine-readable decision.  PRPLL's upstream source and command-line help are
available in the official repository:
<https://github.com/gwoltman/gpuowl>.

Qualification: this protocol may improve throughput after P-1 completes.  It
is not candidate arithmetic, a PRP result, or a primality proof.
