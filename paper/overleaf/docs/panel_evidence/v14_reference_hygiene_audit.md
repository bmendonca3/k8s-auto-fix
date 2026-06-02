# V14 Reference Hygiene Audit

Date: 2026-06-02

## Source Changes

- Refreshed online reference access dates from `Accessed: Oct. 2025` to `Accessed: Jun. 2026`.
- Added a direct Kubernetes Admission Controllers citation for the admission-controller framing.
- Added a Fairwinds Polaris documentation citation for the reproduced Polaris CLI/webhook baseline discussion.
- Updated the dry-run citation from the broad `kubectl` command reference to the specific `kubectl apply` command reference for server-side dry-run.
- Removed the uncited SWE-bench Verified bibliography entry.

## URL Checks

The following new or updated URLs returned HTTP 200 before the edit:

- `https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/`
- `https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/`
- `https://polaris.docs.fairwinds.com/`

## Build and PDF Checks

- Built with `tectonic --keep-logs --outdir build/v14 main.tex`.
- Output PDF: `build/v14/main.pdf`.
- Extracted text: `docs/panel_evidence/pdf_texts/v14_built.txt`.
- Rendered inspection pages: `docs/panel_evidence/images/v14_pages/v14_page_02.png`, `v14_page_14.png`, and `v14_page_15.png`.
- PDF length: 15 pages; extracted text: 9,697 words.
- Unresolved-reference scan found zero `??`, `Figure ??`, or `Table ??` markers.
- Log scan found zero undefined citations, undefined references, or LaTeX errors.
- Artifact-link audit found 107 GitHub blob links and 2 tree links; missing local targets: 0.
- Visual inspection found no obvious overlap or clipping on the updated references/biography pages.
