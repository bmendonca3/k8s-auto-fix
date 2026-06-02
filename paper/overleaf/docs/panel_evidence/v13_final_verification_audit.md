# V13 Final Verification Audit

Date: 2026-06-02

## Build

- Built with `tectonic --keep-logs --outdir build/v13 main.tex`.
- Output PDF: `build/v13/main.pdf`.
- Extracted text: `docs/panel_evidence/pdf_texts/v13_built.txt`.
- Rendered inspection pages: `docs/panel_evidence/images/v13_pages/v13_page_02.png`, `v13_page_10.png`, `v13_page_12.png`, and `v13_page_14.png`.
- PDF length: 15 pages; extracted text: 9,685 words.

## Local Checks

- Unresolved-reference scan found zero `??`, `Figure ??`, or `Table ??` markers.
- Stale-risk wording scan found zero `KEV-derived`, `maps to a CISA`, `Grok/xAI`, `CVE, EPSS`, `data/*.json`, `{eks,gke,aks}`, or old `Y. Li` citation strings.
- GitHub artifact-link audit found 107 blob links and 2 tree links to `bmendonca3/k8s-auto-fix`; missing local targets: 0.
- Visual page inspection found no obvious overlap or clipping on Tables 1, 2, 10, 11, 14, or the corrected references page.
- LaTeX log had no undefined citations, unresolved references, or LaTeX errors. Remaining messages are non-fatal font/layout warnings and rerunfilecheck output.

## External Source Verification

Exact cited source pages were checked with Exa:

- NIST NVD: https://nvd.nist.gov/
- CISA Known Exploited Vulnerabilities Catalog: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- FIRST EPSS: https://www.first.org/epss/
- GenKubeSec: https://arxiv.org/abs/2405.19954
- Kyverno documentation: https://kyverno.io/docs/
- OpenAI Codex Security research preview: https://openai.com/index/codex-security-now-in-research-preview/
- KubeIntellect: https://arxiv.org/abs/2509.02449

KubeIntellect was independently rechecked with Tavily after Exa reported an author mismatch. Tavily's arXiv/PDF extraction confirmed the authors as Mohsen Seyedkazemi Ardebili and Andrea Bartolini, so the V13 bibliography corrects the prior stale `Y. Li et al.` entry to `M. S. Ardebili and A. Bartolini`.

## Artifact-Link Fixes

- Replaced the wildcard `data/*.json` link with the repository `data/` directory.
- Replaced brace-encoded cross-cluster paths with the `data/cross_cluster/` directory and explicit per-cluster summary CSV paths.
