export OPENAI_API_KEY ?=
export RUNPOD_API_KEY ?=

ENDPOINT ?= https://api.openai.com/v1/chat/completions
MODEL ?= gpt-4o-mini

PYTHON ?= python
PIP ?= pip

.PHONY: setup kind-up detect propose verify schedule test e2e smoke-proposer

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

test:
	$(PYTHON) -m unittest discover -s tests -q

e2e:
	$(MAKE) detect && $(MAKE) propose && $(MAKE) verify && $(MAKE) schedule

smoke-proposer:
	curl -s $(ENDPOINT) -H "Authorization: Bearer $(OPENAI_API_KEY)" -H "Content-Type: application/json" \
	 -d '{"model":"$(MODEL)","messages":[{"role":"system","content":"Return ONLY a valid RFC6902 JSON Patch array"},{"role":"user","content":"Manifest: {}\nViolation: test"}]}' >/dev/null || true
