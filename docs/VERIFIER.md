# Verifier Triad and Patch Modes

This project enforces a triad of guardrails before accepting a patch:

- Policy re-check: targeted policy must be cleared (kube-linter/Kyverno re-scan)
- Safety checks: prevent privileged containers, restrict hostPath, drop dangerous capabilities
- Server-side dry-run: validate against the API server without persistence

Why server-side dry-run
- `kubectl apply --dry-run=server` executes admission and schema validation on the API server, catching defaults and conversions while avoiding cluster writes.
- This is the canonical way to validate resource requests prior to applying. See official Kubernetes docs for `--dry-run=server` and server-side apply.

Patch types and defaults
- Default: JSON Patch (RFC6902). Atomic, minimal, auditable operations appropriate for security hardening.
- Fallbacks: JSON Merge Patch or Strategic Merge Patch for list semantics that require merges.
- We measure idempotence (second apply is no-op) and patch minimality (operation count) as quality signals.

References
- Kubernetes apply and dry-run: `kubectl apply --dry-run=server` (Kubernetes documentation)
- Server-side apply historical introduction (Kubernetes blog)

