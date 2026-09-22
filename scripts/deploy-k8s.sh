#!/usr/bin/env bash
# Repeatable HomeHub deployment; suitable after cleanup.sh k8s.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
context=orbstack
manifests=kubernetes
while (($#)); do
  case "$1" in
    --context)
      if (($# < 2)) || [[ "$2" == -* || -z "$2" ]]; then echo "$1 requires a value" >&2; exit 2; fi
      context="$2"
      shift 2 ;;
    -h|--help) echo 'Usage: scripts/deploy-k8s.sh [--context NAME]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
export HOMEHUB_CONTEXT="$context"
k() { kubectl --context "$context" "$@"; }
cd "$ROOT"
# Refuse an impossible topology before modifying any cluster resources.
k get nodes -o json | python3 -c '
import json,sys
nodes=json.load(sys.stdin)["items"]
ready=[n for n in nodes if not n["spec"].get("unschedulable") and any(c["type"]=="Ready" and c["status"]=="True" for c in n["status"].get("conditions",[]))]
if len(ready)!=1: raise SystemExit(f"This deployment supports one Ready schedulable node; found {len(ready)}.")
'
k kustomize "$manifests" >/dev/null
k get storageclass -o json | python3 -c '
import sys,json
items=json.load(sys.stdin)["items"]
if not any(s["metadata"].get("annotations",{}).get("storageclass.kubernetes.io/is-default-class")=="true" for s in items): raise SystemExit("A default StorageClass is required.")
'
echo "Deploying HomeHub: context=$context (single-node)"
if ! k -n cnpg-system get deployment cnpg-controller-manager >/dev/null 2>&1; then
  ./scripts/install-db-operator.sh
fi
k -n cnpg-system rollout status deployment/cnpg-controller-manager --timeout=180s
if ! k -n keda get deployment keda-operator >/dev/null 2>&1; then
  ./scripts/install-signal-scaler.sh
fi
for component in keda-operator keda-metrics-apiserver keda-admission; do
  k -n keda rollout status "deployment/$component" --timeout=180s
done
./scripts/install-metrics-server.sh
k apply -f kubernetes/namespace.yaml
python3 scripts/create-db-secrets.py kubernetes
k apply -k "$manifests"
# The operator reconciles database Pods while retaining PVCs and credentials.
python3 scripts/check-k8s-health.py --context "$context" --timeout 600
