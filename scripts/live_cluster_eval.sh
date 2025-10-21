#!/usr/bin/env bash
set -euo pipefail

# Live-cluster evaluation helper
# - Installs common CRDs (Prometheus, Traefik) for realistic fixtures
# - Seeds namespace-scoped resources
# - Runs the k8s-auto-fix pipeline end-to-end with server-side dry-run enabled

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

kubectl version --client || { echo "kubectl not available" >&2; exit 1; }

echo "[live-eval] Installing common CRDs (Prometheus, Traefik)"
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/prometheus-operator-crd/monitoring.coreos.com_alertmanagers.yaml || true
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/prometheus-operator-crd/monitoring.coreos.com_prometheuses.yaml || true
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/example/prometheus-operator-crd/monitoring.coreos.com_servicemonitors.yaml || true
kubectl apply -f https://raw.githubusercontent.com/traefik/traefik-helm-chart/master/traefik/crds/ingressroutes.yaml || true

echo "[live-eval] Seeding RBAC and default NetworkPolicies"
kubectl apply -f "$ROOT_DIR/infra/fixtures/rbac/placeholder_clusterroles.yaml" || true
kubectl apply -f "$ROOT_DIR/infra/fixtures/network_policies/default-deny.yaml" || true

echo "[live-eval] Detect -> filter -> Propose (rules) -> Verify (server dry-run)"
python -m src.detector.cli --in "$ROOT_DIR/data/manifests" --out "$ROOT_DIR/data/detections_live.json" --jobs 4
# Filter known manual-review policies (e.g., dangling service) to avoid aborting the batch
python - << 'PY'
import json, pathlib
root=pathlib.Path('.');
inp=pathlib.Path('data/detections_live.json');
outp=pathlib.Path('data/detections_live_filtered.json');
data=json.loads(inp.read_text())
def norm(s):
  return (s or '').strip().lower().replace('-', '_')
skip={'dangling_service','non_existent_service_account'}
filtered=[r for r in data if norm(r.get('policy_id')) not in skip]
outp.write_text(json.dumps(filtered, indent=2))
print(f"Filtered detections: kept {len(filtered)} / {len(data)}")
PY
python -m src.proposer.cli --detections "$ROOT_DIR/data/detections_live_filtered.json" --out "$ROOT_DIR/data/patches_live.json" --config "$ROOT_DIR/configs/run_rules.yaml"
python -m src.verifier.cli --patches "$ROOT_DIR/data/patches_live.json" --detections "$ROOT_DIR/data/detections_live_filtered.json" --out "$ROOT_DIR/data/verified_live.json" --include-errors --require-kubectl --enable-rescan --policies-dir "$ROOT_DIR/data/policies/kyverno"

echo "[live-eval] Done. Outputs in data/detections_live.json, data/verified_live.json"
