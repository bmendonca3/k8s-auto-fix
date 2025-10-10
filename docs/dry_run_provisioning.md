# Dry-Run Cluster Provisioning

## Workflow

1. `python scripts/seed_dry_run_cluster.py data/manifests --out data/collected_crds.yaml`
2. `kubectl apply -f data/collected_crds.yaml`
3. Install controllers/webhooks (cert-manager, Argo, Prometheus) matching the manifests.
4. Verify `kubectl api-resources` lists expected CRDs before running Grok verification.

## Optional Helm installs

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set crds.enabled=true
```

Repeat for Argo or other controllers referenced in the dataset.

## Quick dry-run smoke test

Once the CRDs are applied, you can sanity-check the server-side dry-run gate without launching the full Grok sweep:

```bash
python -m src.verifier.cli \
  --patches data/patches.json \
  --detections data/detections.json \
  --out data/verified_dryrun.json \
  --include-errors --require-kubectl \
  --limit 5
```

Adjust `--limit` or add `--id <DET_ID>` to target specific patches while you validate the cluster setup.
