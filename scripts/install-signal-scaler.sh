#!/usr/bin/env sh
set -eu
kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.20.2/keda-2.20.2.yaml
kubectl rollout status deployment/keda-operator -n keda --timeout=600s
kubectl rollout status deployment/keda-metrics-apiserver -n keda --timeout=600s
kubectl rollout status deployment/keda-admission -n keda --timeout=600s
