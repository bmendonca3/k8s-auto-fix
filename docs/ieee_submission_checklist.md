# TCC / ScholarOne Submission Checklist — k8s-auto-fix

## Submission Gate
- Do not submit until IEEE Transactions on Cloud Computing confirms that
  TCC-2025-12-0666 may be resubmitted or reopened as a major revision.
- If permission is denied or the paper must be submitted as a new manuscript,
  update the cover letter and any response text before upload.

## Main Artifacts
- `paper/access.pdf` — final manuscript PDF compiled from `paper/access.tex`.
- `paper/access.tex` — authoritative source for the manuscript.
- `paper/grok_failures_table.tex` — included failure-taxonomy table.
- `docs/reproducibility/baselines.tex` — included baseline table source.
- `figures/*.png` plus author photos in `paper/` — figures and biography images used by the source.
- `paper/cover_letter.md` — TCC resubmission cover-letter draft.
- `paper/overleaf/` — self-contained package when an online TeX upload is needed.

## Rebuild Commands
```
cd paper
./tectonic -X compile access.tex --outdir /tmp/k8s_tcc_build --keep-logs
cd ..
cd paper/overleaf
../tectonic -X compile main.tex --outdir /tmp/k8s_overleaf_build --keep-logs
cd ../..
.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'
python -c "import json; d=json.load(open('data/metrics_schedule_compare.json')); print('FIFO P95:', d['telemetry']['fifo']['top_risk_wait_hours']['p95']); print('Bandit P95:', d['telemetry']['baseline']['top_risk_wait_hours']['p95'])"
python -c "import json; print('Detector F1:', json.load(open('data/eval/detector_metrics.json'))['f1'])"
```

## Portal Checklist
1. Upload `paper/access.pdf` as the main manuscript.
2. Paste or upload `paper/cover_letter.md` only after the resubmission gate is satisfied.
3. Attach supplemental/reproducibility materials if the portal allows them.
4. Complete author and affiliation metadata exactly as in the manuscript.
5. Confirm keywords match the manuscript.
6. Confirm that all reviewer-response claims match the current PDF and artifacts.
7. Retain the portal confirmation email and manuscript ID.
