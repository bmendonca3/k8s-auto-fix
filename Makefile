export OPENAI_API_KEY ?=
export RUNPOD_API_KEY ?=

ENDPOINT ?= https://api.openai.com/v1/chat/completions
MODEL ?= gpt-4o-mini

PYTHON ?= python
PIP ?= pip

.PHONY: setup kind-up detect propose verify schedule test e2e smoke-proposer risk cti queue-init queue-enqueue queue-next metrics benchmark-grok200 benchmark-grok5k benchmark-full benchmark-scheduler benchmark-grok-full update-metrics-docs summarize-failures

JOBS ?= 4
GROK_PROPOSER_CONFIG ?= configs/run_grok.yaml
GROK_VERIFY_FLAGS ?= --include-errors --no-require-kubectl
GROK5K_VERIFY_FLAGS ?= --include-errors --enable-rescan --policies-dir data/policies/kyverno
GROK5K_MIN_ACCEPTANCE ?= 0.75

setup:
	$(PIP) install -r requirements.txt

kind-up:
	./scripts/kind_up.sh

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
	$(PYTHON) -m unittest discover -s tests -q

e2e:
	$(PYTHON) scripts/e2e_smoke.py

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

benchmark-grok200:
	@echo "Running Grok benchmark across 200 detections"
	@[ -n "$$XAI_API_KEY" ] || (echo "XAI_API_KEY environment variable is required for Grok mode" >&2; exit 1)
	$(PYTHON) -c "import itertools, json, pathlib; root = pathlib.Path('data/batch_runs'); detections = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('detections_grok200_batch_*.json')))); target = root / 'detections_grok200.json'; target.write_text(json.dumps(detections, indent=2), encoding='utf-8'); print(f'Wrote {target} with {len(detections)} detections')"
	@rm -f data/batch_runs/patches_grok200.json data/batch_runs/verified_grok200.json data/batch_runs/metrics_grok200.json
	@for f in data/batch_runs/detections_grok200_batch_*.json; do \
		idx=$$(basename $$f .json | sed 's/[^0-9]//g'); \
		echo "Proposing batch $$idx"; \
		$(PYTHON) -m src.proposer.cli --detections $$f --out data/batch_runs/patches_grok200_batch_$${idx}.json --config $(GROK_PROPOSER_CONFIG); \
		echo "Verifying batch $$idx"; \
		$(PYTHON) -m src.verifier.cli --patches data/batch_runs/patches_grok200_batch_$${idx}.json --detections $$f --out data/batch_runs/verified_grok200_batch_$${idx}.json $(GROK_VERIFY_FLAGS); \
	done
	$(PYTHON) -c "import itertools, json, pathlib; root = pathlib.Path('data/batch_runs'); patches = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('patches_grok200_batch_*.json')))); verified = list(itertools.chain.from_iterable(json.load(path.open('r', encoding='utf-8')) for path in sorted(root.glob('verified_grok200_batch_*.json')))); (root / 'patches_grok200.json').write_text(json.dumps(patches, indent=2), encoding='utf-8'); (root / 'verified_grok200.json').write_text(json.dumps(verified, indent=2), encoding='utf-8'); print(f'Merged {len(patches)} patches and {len(verified)} verifier records')"
	$(PYTHON) -m src.eval.metrics --detections data/batch_runs/detections_grok200.json --patches data/batch_runs/patches_grok200.json --verified data/batch_runs/verified_grok200.json --out data/batch_runs/metrics_grok200.json
	$(PYTHON) scripts/update_metrics_docs.py

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
