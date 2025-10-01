#!/bin/bash
set -euo pipefail

NAME="auto-fix-cluster"
CONFIG_FILE="kind-config.yaml"

cat > "${CONFIG_FILE}" <<KINDCFG
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
KINDCFG

kind create cluster --name "${NAME}" --config "${CONFIG_FILE}"

kubectl cluster-info
kubectl get nodes

kubectl config use-context "kind-${NAME}"
