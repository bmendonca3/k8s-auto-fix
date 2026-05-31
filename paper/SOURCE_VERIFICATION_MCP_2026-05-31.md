# Source Verification Snapshot

Generated: 2026-05-31.
Scope: active citations in `paper/access.tex`, `paper/overleaf/paper/access.tex`,
`paper/references.bib`, and `paper/overleaf/paper/references.bib`.

This is a local audit note only. Do not upload it with the TCC packet.

## Current Answer

Yes: the active manuscript currently has **38 cited keys**, **38 inline
`\bibitem`s**, and **38 matching BibTeX mirror entries**. The local citation
graph has:

- cited-but-undefined keys: 0
- uncited active bibitems: 0
- standalone/Overleaf key drift: 0
- active cited bibliography entries with recorded verification evidence: 38/38

The machine-readable record is
`paper/source_verification_mcp_2026-05-31.json`. It records the same 38/38 count
and the post-hardening verification status.

## Active Keys

`aardvark`, `artifacthub`, `auer2002`, `borg`, `cis_benchmarks`, `cisa_kev`,
`epss`, `grype`, `joseph2016`, `k8s_admission`, `k8s_seccomp`,
`k8s_security_context`, `kube_linter_docs`, `kubectl_reference`,
`kubeintellect`, `kubellm`, `kyverno_docs`, `kyverno_mutate`, `lian2023`,
`llmsecconfig`, `malul2024`, `minna2024`, `nvd`, `opa_gatekeeper`,
`patch_overfitting_fse2024`, `polaris`, `pss`, `repairagent_icse2025`,
`rfc6902`, `rust_lancet_icse2024`, `saavedra2022`, `shamim2020`, `shu2017`,
`swe_bench_verified`, `trivy`, `ullah2024`, `xai_pricing`, `xia2023`.

## Verification Coverage

The following groups have current recorded evidence:

| Group | Keys | Evidence status |
|---|---|---|
| Kubernetes, Kyverno, OPA/Gatekeeper, kube-linter, kubectl, RFC, CIS/NVD/CISA/FIRST/Aqua/Anchore/Fairwinds/Artifact Hub docs | `cis_benchmarks`, `pss`, `k8s_admission`, `opa_gatekeeper`, `kube_linter_docs`, `polaris`, `k8s_security_context`, `rfc6902`, `kubectl_reference`, `k8s_seccomp`, `nvd`, `cisa_kev`, `epss`, `trivy`, `grype`, `kyverno_docs`, `kyverno_mutate`, `artifacthub` | HTTP/search/MCP evidence recorded; no active unresolved citation failures. |
| OpenAI/xAI web references | `aardvark`, `swe_bench_verified`, `xai_pricing` | Exa/Tavily confirmed the relevant OpenAI/xAI pages. Direct local HTTP can return 403 on OpenAI pages, so these are recorded as search/extract confirmed rather than direct-fetch failures. |
| Kubernetes/LLM/security academic sources | `llmsecconfig`, `minna2024`, `lian2023`, `malul2024`, `kubellm`, `kubeintellect`, `ullah2024`, `shamim2020`, `saavedra2022`, `xia2023`, `patch_overfitting_fse2024`, `rust_lancet_icse2024`, `repairagent_icse2025`, `shu2017` | DOI/arXiv/publisher/search evidence recorded; later precision pass corrected KubeLLM, GLITCH, RepairAgent, and Minna metadata. |
| Scheduling/bandit foundations | `auer2002`, `joseph2016`, `borg` | Publisher/proceedings/search evidence recorded. |

## Fresh MCP Spot Checks

Fresh Exa/Tavily checks in this cleanup pass re-confirmed the previously weaker
or high-value source assumptions:

- `kube_linter_docs`: Exa fetched `https://docs.kubelinter.io/` with the
  expected KubeLinter built-in checks and Kubernetes YAML/Helm chart linting
  content.
- `swe_bench_verified`: Tavily extracted the OpenAI SWE-bench Verified page,
  including the human-validated 500-sample subset description.
- `aardvark`: current active URL is the OpenAI Codex Security research-preview
  page, formerly Aardvark; prior Exa/Tavily extraction confirmed that rename.
- `xai_pricing`: prior Exa/Tavily/current-web checks confirmed Grok 4.3 pricing,
  configurable reasoning, and billable reasoning/total-token semantics.
- `k8s_admission`: Kubernetes admission-control docs confirmed mutating
  admission before validating admission.
- `kyverno_mutate`: Kyverno docs confirmed strategic-merge, JSONPatch, foreach,
  mutate-existing, and dry-run/GitOps mutation behavior.

## Sources Considered But Not Retained

These were verified during the hardening pass but deliberately omitted from the
active 17-page manuscript:

- Checkov official docs: omitted because Minna et al. provides stronger
  peer-reviewed Checkov/KICS Artifact Hub grounding.
- KICS official docs: same rationale as Checkov.
- Gatekeeper mutation docs: omitted after the admission-engine paragraph was
  tightened to the higher-level Gatekeeper citation.
- Kubernetes MutatingAdmissionPolicy API docs: omitted after compressing the MAP
  sentence to avoid an 18-page regression.

## Remaining Non-Source Gaps

No active source is currently unverified in the local record. The still-open
submission gaps are not source-validity gaps: TCC/EIC permission, final
portal-bound packet review, optional named-agent head-to-head, novelty judgment,
and clean source-package assembly. Track those in
`paper/SUBMISSION_GAP_REGISTER.md` and `paper/REVISION_TRACKING.md`.
