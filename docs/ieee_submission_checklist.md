# IEEE Access Submission Checklist — k8s-auto-fix

## Artifacts
- `paper/access.pdf` — final manuscript (compiled with `pdflatex access.tex` repeated twice).
- `paper/cover_letter.md` — submission letter (copy into the IEEE Access portal or convert to PDF).
- `data/grok5k_telemetry.json`, `data/grok1k_telemetry.json` — referenced telemetry supporting Grok evaluations.
- `data/eval/detector_metrics.json` — detector precision/recall/F1 evidence.
- `data/metrics_schedule_compare.json` — scheduler benchmarks (FIFO vs bandit).
- `docs/ablation_rules_vs_grok.md` — rules vs Grok ablation notes cited in the manuscript.
- Optional supplementary bundle: compress `data/`, `docs/`, and `scripts/` subsets as permitted by IEEE Access.

## Rebuild Commands
```
cd paper
pdflatex access.tex
pdflatex access.tex
cd ..
python -m unittest tests.test_verifier
python -c "import json, sys; d=json.load(open('data/metrics_schedule_compare.json')); print('FIFO P95:', d['telemetry']['fifo']['top_risk_wait_hours']['p95']); print('Bandit P95:', d['telemetry']['baseline']['top_risk_wait_hours']['p95'])"
python -c "import json; print('Detector F1:', json.load(open('data/eval/detector_metrics.json'))['f1'])"
ls -lh data/grok*_telemetry.json
```

## Portal Checklist
1. Upload `access.pdf` as the main manuscript.
2. Provide the cover letter text (`paper/cover_letter.md`).
3. Attach supplementary material bundle if allowed (telemetry JSON, scripts).
4. Complete author/affiliation metadata:
   - Brian Mendonca (Corresponding author)
   - Vijay K. Madisetti
5. Confirm keywords match the manuscript and template.
6. Review DOI placeholder (`\doi{DOI: TBD}`) — update once assigned by IEEE Access.
7. Submit and retain the confirmation email/ID.
