export OPENAI_API_KEY ?=
export RUNPOD_API_KEY ?=

ENDPOINT ?= https://api.openai.com/v1/chat/completions
MODEL ?= gpt-4o-mini

PYTHON ?= python
PIP ?= pip

.PHONY: setup kind-up detect propose verify schedule test e2e smoke-proposer risk cti queue-init queue-enqueue queue-next metrics

setup:
	$(PIP) install -r requirements.txt

kind-up:
	./scripts/kind_up.sh

detect:
	$(PYTHON) -m src.detector.cli --in data/manifests --out data/detections.json

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
	$(MAKE) detect && $(MAKE) propose && $(MAKE) verify && $(MAKE) schedule

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
	$(PYTHON) -m src.eval.metrics run --detections data/detections.json --patches data/patches.json --verified data/verified.json --out data/metrics.json
