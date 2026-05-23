# Artifact Policy

This repository includes both source material and research artifacts. Keep the
tracked set small enough to review while preserving enough evidence to reproduce
paper claims and pipeline metrics.

## Retention Guidelines

- Keep canonical inputs in git when they are small, reusable, and required for
  tests or reproduction. This includes curated manifests, policies, schemas, and
  fixture data under `data/`.
- Keep generated outputs in git only when they are cited by the paper, used by a
  documented reproduction command, or needed as compact regression evidence.
  Prefer compressed JSON for large machine-readable outputs.
- Treat namespaced benchmark outputs as raw validation evidence when a review
  packet, validation note, or paper claim cites them. Retaining those artifacts
  does not by itself promote their metrics into the manuscript; the citing
  document should state whether the run is canonical, supplemental, or
  validation-only.
- Keep logs only when they are curated evidence for a documented run. Do not add
  ad hoc local logs, secrets, API responses with tokens, or full terminal dumps.
- Keep archives only as intentional release or evidence bundles. Prefer external
  release assets or object storage for large bundles that can be regenerated.
- Keep figures and paper outputs that are part of the current manuscript or
  appendix. Generated LaTeX scratch files should stay ignored unless they are
  deliberately used as reproducibility evidence.
- Keep runtime state such as queue databases, local package installers, and
  machine metadata out of new commits unless there is a specific reproduction
  reason and the artifact is documented.

## Artifact Index

Use `scripts/artifact_index.py` to inventory tracked artifact-like files. The
script is standard-library only and reads `git ls-files`, so it reports tracked
files and tracked symlink entries rather than untracked scratch output.

By default it writes CSV to stdout:

```bash
python scripts/artifact_index.py
```

For a bounded smoke check:

```bash
python scripts/artifact_index.py --limit 10
```

To write an index without adding another tracked artifact, write under ignored
`tmp/`:

```bash
python scripts/artifact_index.py --out tmp/artifact-index.csv
```

The CSV columns are:

- `path` - repository-relative tracked path.
- `category` - coarse retention bucket such as `data-input`,
  `generated-output`, `log`, `archive`, `figure`, `paper-output`,
  `runtime-state`, `binary-package`, or `local-metadata`.
- `kind` - `file` or `symlink`.
- `size_bytes` - size of the file bytes, or symlink target text for symlinks.
- `sha256` - SHA-256 digest of the file bytes, or symlink target text for
  symlinks.

Review the index before adding or refreshing large artifacts. If a file is not
required by a reproduction path or cited result, prefer documenting where it can
be regenerated instead of committing it.

## Traceability Records

Use `scripts/artifact_traceability.py` when a review packet or reproduction
manifest needs to prove exactly which generated files were inspected.

```bash
python scripts/artifact_traceability.py \
  --artifact data/patches.json \
  --producer "make propose" \
  --category generated-output
```

The default output is JSON with path, absolute path, presence, kind, size,
SHA-256, producer, category, and note fields. Symlinks are hashed as link
entries rather than target file bytes, matching the artifact index behavior.
Use `--format markdown` for an operator review table, or `--allow-missing` when
documenting expected-but-not-yet-created outputs in a dry-run manifest.
