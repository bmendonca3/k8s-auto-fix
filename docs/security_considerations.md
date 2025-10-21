# Secret and Credential Hygiene

`src/proposer/cli.py` enforces secret hygiene in two layers:

1. `env_var_secret` policy detects environment variables with secret-like names and rewrites them to use `valueFrom.secretKeyRef`, auto-selecting or sanitising secret names via `_select_secret_reference` and `_sanitize_secret_key`.
2. `_sanitize_dns_subdomain` ensures any generated Secret names conform to Kubernetes naming rules; leaking of literal credentials is prevented because plain-text values are removed from the patch payload (`_patch_env_var_secret`).

Artifacts recorded in `data/patches.json` exclude raw secret material, and `tests/test_proposer.py::SecretPatchTests` exercises the guard to ensure sanitisation remains intact.
