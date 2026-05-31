export OPENAI_API_KEY ?=
export RUNPOD_API_KEY ?=

ENDPOINT ?= https://api.openai.com/v1/chat/completions
MODEL ?= gpt-4o-mini

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then printf '%s\n' .venv/bin/python; else command -v python3 || command -v python; fi)
PIP ?= $(PYTHON) -m pip

.PHONY: setup doctor validate-configs docs-link-check metrics-consistency submission-packet-check secret-scan clean-generated kind-up fixtures reproducible-report detect propose verify schedule test artifact-test e2e pipeline-plan pipeline-manifest-smoke pipeline-status-smoke tiny-regression artifact-index-smoke artifact-traceability-smoke evidence-manifest-smoke evidence-manifest-pipeline-smoke evidence-manifest-claims-smoke evidence-manifest-claims-enforce gitops-plan-smoke patch-diff-smoke verifier-report scheduler-explain-smoke scheduler-batches-smoke queue-report-smoke review-packet-smoke review-packet-concise-smoke review-packet-rollout-smoke smoke-proposer risk cti queue-init queue-enqueue queue-next metrics benchmark-grok43-50 benchmark-grok43-200 benchmark-grok200 benchmark-grok5k benchmark-full benchmark-scheduler benchmark-grok-full update-metrics-docs summarize-failures paper baselines baseline-kyverno baseline-polaris baseline-map baseline-llmsec reproduce-all live-eval

JOBS ?= 4
GROK_PROPOSER_CONFIG ?= configs/run_grok.yaml
GROK_VERIFY_FLAGS ?= --include-errors --no-require-kubectl
GROK5K_VERIFY_FLAGS ?= --include-errors --enable-rescan --policies-dir data/policies/kyverno
GROK5K_MIN_ACCEPTANCE ?= 0.75
GROK43_RUN_DATE ?= $(shell date +%Y%m%d)
GROK43_JOBS ?= 1
GROK43_BATCH_SIZE ?= 25
GROK43_SOURCE_GLOB ?= data/batch_runs/grok_5k/detections_grok5k_batch_*.json
GROK43_TOOL_CACHE ?= tmp/tool-cache/bin
GROK43_KUBE_LINTER_CMD ?= $(GROK43_TOOL_CACHE)/kube-linter
GROK43_KYVERNO_CMD ?= $(GROK43_TOOL_CACHE)/kyverno
GROK43_RESUME ?=

setup:
	$(PIP) install -r requirements.txt

doctor:
	$(PYTHON) scripts/doctor.py

validate-configs:
	$(PYTHON) scripts/validate_configs.py

docs-link-check:
	$(PYTHON) scripts/check_docs_links.py README.md docs configs scripts/README.md data/README.md

metrics-consistency:
	$(PYTHON) scripts/check_metrics_consistency.py

submission-packet-check:
	$(PYTHON) scripts/check_submission_packet.py

secret-scan:
	$(PYTHON) scripts/scan_secrets.py

clean-generated:
	$(PYTHON) scripts/clean_generated.py

kind-up:
	./scripts/kind_up.sh

fixtures:
	kubectl apply -f infra/fixtures/rbac/placeholder_clusterroles.yaml
	kubectl apply -f infra/fixtures/network_policies/default-deny.yaml

reproducible-report:
	$(PYTHON) scripts/build_repro_bundle.py

detect:
	$(PYTHON) -m src.detector.cli --in data/manifests --out data/detections.json --jobs $(JOBS)

propose:
	$(PYTHON) -m src.proposer.cli --detections data/detections.json --out data/patches.json --config configs/run.yaml

verify:
	$(PYTHON) -m src.verifier.cli --patches data/patches.json --out data/verified.json --detections data/detections.json

schedule:
	$(PYTHON) -m src.scheduler.cli --verified data/verified.json --out data/schedule.json --detections data/detections.json

risk:
	$(PYTHON) -m src.risk.cli --detections data/detections.json --out data/risk.json

cti:
	$(PYTHON) -m src.risk.fetch_cti fetch

schedule-with-risk:
	$(PYTHON) -m src.scheduler.cli --verified data/verified.json --out data/schedule.json --detections data/detections.json --risk data/risk.json

test:
	$(PYTHON) -m pytest -q

artifact-test:
	K8S_AUTO_FIX_ARTIFACT_TESTS=1 $(PYTHON) -m unittest tests.test_patch_minimality -q

e2e:
	$(PYTHON) scripts/e2e_smoke.py

pipeline-plan:
	$(PYTHON) scripts/run_pipeline.py --dry-run

pipeline-manifest-smoke:
	$(PYTHON) scripts/run_pipeline.py --dry-run --manifest-out tmp/pipeline-manifest.json

pipeline-status-smoke:
	$(PYTHON) scripts/run_pipeline.py --dry-run --status-out tmp/pipeline-status.json >/dev/null

tiny-regression:
	$(PYTHON) scripts/run_tiny_regression.py

artifact-index-smoke:
	$(PYTHON) scripts/artifact_index.py --limit 10

artifact-traceability-smoke:
	$(PYTHON) scripts/artifact_traceability.py --artifact data/patches.json --producer "make propose" --category generated-output >/dev/null

evidence-manifest-smoke:
	$(PYTHON) scripts/build_evidence_manifest.py --artifact data/patches.json --producer-command "make propose" --claim patch-output --category generated-output --out tmp/evidence-manifest-smoke.json

evidence-manifest-pipeline-smoke:
	$(PYTHON) scripts/run_pipeline.py --dry-run --manifest-out tmp/pipeline-manifest.json --status-out tmp/pipeline-status.json >/dev/null
	$(PYTHON) scripts/build_evidence_manifest.py --artifact data/patches.json --producer-command "make propose" --claim patch-output --category generated-output --pipeline-manifest tmp/pipeline-manifest.json --pipeline-status tmp/pipeline-status.json --out tmp/evidence-manifest-pipeline-smoke.json

evidence-manifest-claims-smoke:
	mkdir -p tmp
	printf '%s\n' '{"claims":[{"id":"patch-output","title":"Patch output exists"},{"id":"uncovered-claim","title":"Uncovered smoke claim"}]}' > tmp/claims-table-smoke.json
	$(PYTHON) scripts/build_evidence_manifest.py --artifact data/patches.json --producer-command "make propose" --claim patch-output --category generated-output --claims-table tmp/claims-table-smoke.json --out tmp/evidence-manifest-claims-smoke.json

evidence-manifest-claims-enforce:
	mkdir -p tmp
	$(PYTHON) scripts/build_evidence_manifest.py --spec data/eval/paper_evidence_spec.json --claims-table data/eval/paper_claims.json --fail-on-uncovered-claims --out tmp/evidence-manifest-claims-enforce.json

gitops-plan-smoke:
	$(PYTHON) scripts/gitops_writeback.py --detections data/detections.json --verified data/verified.json --repo-root . --plan-out tmp/gitops-writeback-plan-smoke.json >/dev/null

patch-diff-smoke:
	$(PYTHON) scripts/render_patch_diff.py --detections data/detections.json --patches data/patches.json --id 002

verifier-report:
	$(PYTHON) scripts/verifier_report.py data/verified.json --max-groups 5 --max-ids 5

scheduler-explain-smoke:
	printf '%s\n' '[{"id":"demo","risk":80,"probability":0.9,"expected_time":10,"kev":true}]' | $(PYTHON) scripts/scheduler_explain.py --json >/dev/null

scheduler-batches-smoke:
	$(PYTHON) -m src.scheduler.cli --verified data/verified.json --detections data/detections.json --risk data/risk.json --out tmp/schedule-smoke.json --batch-group-by policy --batch-max-size 3 --batches-out tmp/schedule-batches-smoke.json >/dev/null

queue-report-smoke:
	$(PYTHON) scripts/queue_report.py data/queue.db --json >/dev/null

review-packet-smoke:
	$(PYTHON) scripts/build_review_packet.py --detections data/detections.json --patches data/patches.json --verified data/verified.json --schedule data/schedule.json --artifact data/patches.json --id 002 --max-diffs 1 >/dev/null

review-packet-concise-smoke:
	$(PYTHON) scripts/build_review_packet.py --detections data/detections.json --patches data/patches.json --verified data/verified.json --schedule data/schedule.json --artifact data/patches.json --id 002 --max-diffs 1 --markdown-mode concise >/dev/null

review-packet-rollout-smoke:
	$(PYTHON) -m src.scheduler.cli --verified data/verified.json --detections data/detections.json --risk data/risk.json --out tmp/schedule-rollout-smoke.json --batch-group-by namespace --batch-max-size 3 --batches-out tmp/schedule-rollout-batches-smoke.json >/dev/null
	$(PYTHON) scripts/build_review_packet.py --detections data/detections.json --patches data/patches.json --verified data/verified.json --schedule tmp/schedule-rollout-smoke.json --batches tmp/schedule-rollout-batches-smoke.json --rollout-max-count 3 --rollout-max-policies 2 --id 002 --max-diffs 1 --markdown-mode concise >/dev/null

smoke-proposer:
	curl -s $(ENDPOINT) -H "Authorization: Bearer $(OPENAI_API_KEY)" -H "Content-Type: application/json" \
	 -d '{"model":"$(MODEL)","messages":[{"role":"system","content":"Return ONLY a valid RFC6902 JSON Patch array"},{"role":"user","content":"Manifest: {}\nViolation: test"}]}' >/dev/null || true

queue-init:
	$(PYTHON) -m src.scheduler.queue_cli init --db data/queue.db

queue-enqueue:
	$(PYTHON) -m src.scheduler.queue_cli enqueue --db data/queue.db --verified data/verified.json --detections data/detections.json --risk data/risk.json

queue-next:
	$(PYTHON) -m src.scheduler.queue_cli next --db data/queue.db

metrics:
	$(PYTHON) -m src.eval.metrics --detections data/detections.json --patches data/patches.json --verified data/verified.json --out data/metrics.json

benchmark-grok43-50:
	@echo "Running safe Grok 4.3 benchmark across 50 detections"
	@[ -n "$$XAI_API_KEY" ] || (echo "XAI_API_KEY environment variable is required for Grok mode" >&2; exit 1)
	$(PYTHON) scripts/run_grok43_benchmark.py \
		--limit 50 \
		--run-id grok43_$(GROK43_RUN_DATE)_50 \
		--source-glob "$(GROK43_SOURCE_GLOB)" \
		--batch-size $(GROK43_BATCH_SIZE) \
		--jobs $(GROK43_JOBS) \
		--kube-linter-cmd $(GROK43_KUBE_LINTER_CMD) \
		--kyverno-cmd $(GROK43_KYVERNO_CMD) \
		$(GROK43_RESUME)

benchmark-grok43-200:
	@echo "Running safe Grok 4.3 benchmark across 200 detections"
	@[ -n "$$XAI_API_KEY" ] || (echo "XAI_API_KEY environment variable is required for Grok mode" >&2; exit 1)
	$(PYTHON) scripts/run_grok43_benchmark.py \
		--limit 200 \
		--run-id grok43_$(GROK43_RUN_DATE)_200 \
		--source-glob "$(GROK43_SOURCE_GLOB)" \
		--batch-size $(GROK43_BATCH_SIZE) \
		--jobs $(GROK43_JOBS) \
		--kube-linter-cmd $(GROK43_KUBE_LINTER_CMD) \
		--kyverno-cmd $(GROK43_KYVERNO_CMD) \
		$(GROK43_RESUME)

benchmark-grok200:
	@echo "Running Grok benchmark across 200 detections"
	@[ -n "$$XAI_API_KEY" ] || (echo "XAI_API_KEY environment variable is required for Grok mode" >&2; exit 1)
	@rm -f data/batch_runs/patches_grok200_batch_*.json data/batch_runs/verified_grok200_batch_*.json || true
	$(PYTHON) -c "import itertools, json, pathlib; root = pathlib.Path('data/batch_runs'); detections = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('detections_grok200_batch_*.json')))); target = root / 'detections_grok200.json'; target.write_text(json.dumps(detections, indent=2), encoding='utf-8'); print(f'Wrote {target} with {len(detections)} detections')"
	@rm -f data/batch_runs/patches_grok200.json data/batch_runs/verified_grok200.json data/batch_runs/metrics_grok200.json
	@for f in data/batch_runs/detections_grok200_batch_*.json; do \
		idx=$$(basename $$f .json | sed 's/[^0-9]//g'); \
		patches_path=data/batch_runs/patches_grok200_batch_$${idx}.json; \
		verified_path=data/batch_runs/verified_grok200_batch_$${idx}.json; \
		echo "Proposing batch $$idx"; \
		if $(PYTHON) -m src.proposer.cli --detections $$f --out $$patches_path --config $(GROK_PROPOSER_CONFIG); then \
		  if [ -f "$$patches_path" ]; then \
		    echo "Verifying batch $$idx"; \
		    $(PYTHON) -m src.verifier.cli --patches $$patches_path --detections $$f --out $$verified_path $(GROK_VERIFY_FLAGS); \
		  else \
		    echo "[warn] Patches missing for $$idx; skipping verify"; \
		  fi; \
		else \
		  echo "[warn] Proposer failed for $$idx; skipping verify"; \
		fi; \
	done
	$(PYTHON) -c "import itertools, json, pathlib; root = pathlib.Path('data/batch_runs'); patches = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('patches_grok200_batch_*.json')))); verified = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('verified_grok200_batch_*.json')))); (root / 'patches_grok200.json').write_text(json.dumps(patches, indent=2), encoding='utf-8'); (root / 'verified_grok200.json').write_text(json.dumps(verified, indent=2), encoding='utf-8'); print(f'Merged {len(patches)} patches and {len(verified)} verifier records')"
	$(PYTHON) -m src.eval.metrics --detections data/batch_runs/detections_grok200.json --patches data/batch_runs/patches_grok200.json --verified data/batch_runs/verified_grok200.json --out data/batch_runs/metrics_grok200.json
	$(PYTHON) scripts/update_metrics_docs.py || true

benchmark-grok5k:
	@echo "Running Grok benchmark across 5k detections"
	@[ -n "$$XAI_API_KEY" ] || (echo "XAI_API_KEY environment variable is required for Grok mode" >&2; exit 1)
	$(PYTHON) scripts/process_batches.py \
		--detections-glob "data/batch_runs/grok_5k/detections_grok5k_batch_*.json" \
		--patches-dir data/batch_runs/grok_5k \
		--verified-dir data/batch_runs/grok_5k \
		--config $(GROK_PROPOSER_CONFIG) \
		--jobs $(JOBS) \
		--resume \
		--verifier-extra $(GROK5K_VERIFY_FLAGS) --jobs $(JOBS)
	$(PYTHON) scripts/merge_batches.py "data/batch_runs/grok_5k/detections_grok5k_batch_*.json" data/batch_runs/grok_5k/detections_grok5k.json
	$(PYTHON) scripts/merge_batches.py "data/batch_runs/grok_5k/patches_grok5k_batch_*.json" data/batch_runs/grok_5k/patches_grok5k.json
	$(PYTHON) scripts/merge_batches.py "data/batch_runs/grok_5k/verified_grok5k_batch_*.json" data/batch_runs/grok_5k/verified_grok5k.json
	$(PYTHON) -m src.eval.metrics \
		--detections data/batch_runs/grok_5k/detections_grok5k.json \
		--patches data/batch_runs/grok_5k/patches_grok5k.json \
		--verified data/batch_runs/grok_5k/verified_grok5k.json \
		--out data/batch_runs/grok_5k/metrics_grok5k.json
	$(PYTHON) scripts/summarize_failures.py \
		--verified-glob "data/batch_runs/grok_5k/verified_grok5k_batch_*.json" \
		--detections-glob "data/batch_runs/grok_5k/detections_grok5k_batch_*.json"
	$(PYTHON) -c "import json, pathlib; metrics_path = pathlib.Path('data/batch_runs/grok_5k/metrics_grok5k.json'); \
assert metrics_path.exists(), 'metrics_grok5k.json missing'; \
metrics = json.loads(metrics_path.read_text()); \
rate = float(metrics.get('auto_fix_rate', 0.0)); \
threshold = float('$(GROK5K_MIN_ACCEPTANCE)'); \
print(f'Grok 5k acceptance rate: {rate:.2%} (threshold {threshold:.2%})'); \
import sys; sys.exit(0 if rate >= threshold else 1)"

benchmark-full: detect
	@echo "Running full rules benchmark with $(JOBS) parallel workers"
	$(PYTHON) scripts/parallel_runner.py propose --detections data/detections.json --config configs/run_rules.yaml --out data/patches_rules_full.json --jobs $(JOBS)
	$(PYTHON) scripts/parallel_runner.py verify --patches data/patches_rules_full.json --detections data/detections.json --out data/verified_rules_full.json --jobs $(JOBS) --extra-args --include-errors --no-require-kubectl
	$(PYTHON) -m src.eval.metrics --detections data/detections.json --patches data/patches_rules_full.json --verified data/verified_rules_full.json --out data/metrics_rules_full.json
	$(PYTHON) scripts/update_metrics_docs.py

benchmark-grok-full:
	@echo "Running Grok benchmark across the full corpus (1313 detections)"
	$(PYTHON) scripts/split_detections.py data/detections.json data/batch_runs/grok_full detections_grok_full_batch 40
	@set -e; for f in data/batch_runs/grok_full/detections_grok_full_batch_*.json; do \
	  idx=$$(basename $$f .json | sed 's/[^0-9]//g'); \
	  echo "[Grok] Proposing batch $$idx"; \
	  $(PYTHON) -m src.proposer.cli --detections $$f --out data/batch_runs/grok_full/patches_grok_full_batch_$${idx}.json --config configs/run.yaml; \
	done
	@set -e; for f in data/batch_runs/grok_full/patches_grok_full_batch_*.json; do \
	  idx=$$(basename $$f .json | sed 's/[^0-9]//g'); \
	  echo "[Grok] Verifying batch $$idx"; \
	  $(PYTHON) -m src.verifier.cli --patches $$f --detections data/batch_runs/grok_full/detections_grok_full_batch_$${idx}.json --out data/batch_runs/grok_full/verified_grok_full_batch_$${idx}.json --include-errors --no-require-kubectl; \
	done
	$(PYTHON) scripts/merge_batches.py "data/batch_runs/grok_full/patches_grok_full_batch_*.json" data/batch_runs/grok_full/patches_grok_full.json
	$(PYTHON) scripts/merge_batches.py "data/batch_runs/grok_full/verified_grok_full_batch_*.json" data/batch_runs/grok_full/verified_grok_full.json
	$(PYTHON) -m src.eval.metrics --detections data/detections.json --patches data/batch_runs/grok_full/patches_grok_full.json --verified data/batch_runs/grok_full/verified_grok_full.json --out data/batch_runs/grok_full/metrics_grok_full.json
	$(PYTHON) scripts/update_metrics_docs.py

benchmark-scheduler:
	$(PYTHON) scripts/compare_schedulers.py --verified data/verified_rules_full.json --detections data/detections.json --risk data/risk.json --out data/metrics_schedule_compare.json
	$(PYTHON) scripts/update_metrics_docs.py

update-metrics-docs:
	$(PYTHON) scripts/update_metrics_docs.py

summarize-failures:
	$(PYTHON) scripts/summarize_failures.py \
		--verified-glob "data/batch_runs/grok_5k/verified_grok5k_batch_*.json" \
		--detections-glob "data/batch_runs/grok_5k/detections_grok5k_batch_*.json"

# Build the paper PDF (outputs to paper/)
paper:
	cd paper && pdflatex -interaction=nonstopmode access.tex || true
	cd paper && pdflatex -interaction=nonstopmode access.tex || true

# Baselines (simulation by default)
baseline-kyverno:
	$(PYTHON) scripts/run_kyverno_baseline.py --detections data/detections.json --output data/baselines/kyverno_baseline.csv --simulate

baseline-polaris:
	$(PYTHON) scripts/run_polaris_baseline.py --detections data/detections.json --output data/baselines/polaris_baseline.csv --simulate

baseline-map:
	$(PYTHON) scripts/run_mutatingadmission_baseline.py --detections data/detections.json --output data/baselines/map_baseline.csv --simulate

baseline-llmsec:
	@[ -n "$$OPENAI_API_KEY" ] || (echo "OPENAI_API_KEY is required for LLMSecConfig slice" >&2; exit 0)
	$(PYTHON) scripts/run_llmsecconfig_slice.py --detections data/detections.json --out data/baselines/llmsecconfig_slice.csv --limit 500

baselines: baseline-kyverno baseline-polaris baseline-map

reproduce-all:
	bash ./scripts/reproduce_all.sh

live-eval:
	./scripts/live_cluster_eval.sh
