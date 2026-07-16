# Overleaf Canonical-Source Workflow

Overleaf is the only manuscript editing surface. GitHub repositories are
verified downstream mirrors; do not edit a mirror and push it back to
Overleaf.

## Release order

1. Freeze artifact evidence in commit `A` and create an immutable release tag
   `R` that resolves to `A`.
2. Update the canonical Overleaf source so every artifact link names `A` (and
   records `R` as the human-readable release identifier).
3. Compile and inspect the canonical PDF in Overleaf.
4. Import the exact Overleaf source and canonical PDF into the paper repository
   as commit `P`, recording source-tree and PDF hashes in its sync lock.
5. Import commit `P` into `paper/overleaf/` here. This downstream mirror commit
   `B` must not move tag `R` or change evidence outside the manuscript mirror
   and its generated inventory.

This order avoids a circular reference: the manuscript cites immutable
evidence commit `A`; the later mirror commit `B` may contain the manuscript but
does not change the evidence release.

## Required checks

- `make metrics-consistency` passes at evidence commit `A`.
- The paper source contains no stale full-corpus metrics, UCB/online-learning
  claims, or synthetic operator-study claims.
- The scheduler comparison exactly regenerates from the declared historical
  queue snapshot and records zero initial ages and exploration inputs.
- Figure 4 contains only the matched 5,000-record rules+guardrails and
  Grok+rule-guardrails snapshots.
- The Overleaf build completes without missing files or unresolved references,
  and every rendered page is inspected.
- After the downstream import, run
  `python scripts/check_metrics_consistency.py --include-manuscript` and
  `make paper-build-check`.
- The imported source/PDF hashes match the paper repository's sync lock.

## Credential handling

Overleaf Git credentials belong in the operating system credential manager or
an already-authenticated browser/session. Never place a token in a remote URL,
shell command, Git configuration, repository file, sync lock, test fixture,
CI secret printed to logs, or agent prompt. The lock records only revisions and
content hashes.

## Recovery

If Overleaf and a mirror diverge, stop and compare revisions and hashes. Treat
Overleaf as canonical for manuscript text and artifact commit `A` as canonical
for evidence. Re-import in the order above; do not merge the divergent trees or
move the evidence tag.
