#!/usr/bin/env sh
set -eu

echo "Checking Python syntax"
python3 -m compileall -q services

echo "Checking Kubernetes manifests"
kubectl kustomize kubernetes >/dev/null

echo "Checking frontend build"
npm --prefix frontend run build

echo "Static checks passed"

