#!/usr/bin/env bash
set -euo pipefail
context="${HOMEHUB_CONTEXT:-orbstack}"
k() { kubectl --context "$context" "$@"; }
# Reuse an existing provider (including managed-cluster add-ons).
if ! k get apiservice v1beta1.metrics.k8s.io >/dev/null 2>&1; then
  k version -o json | python3 -c '
import json,sys,re
v=json.load(sys.stdin)["serverVersion"]
version=(int(v["major"]), int(re.match(r"[0-9]+",v["minor"])[0]))
if version < (1,34): raise SystemExit("Metrics Server 0.9.0 requires Kubernetes 1.34+; install a compatible Metrics API provider first.")
'
  manifest=$(mktemp)
  trap 'rm -f "$manifest"' EXIT
  k create --dry-run=client --validate=false -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml -o json > "$manifest"
  # Keep kubelet TLS verification enabled; trust the cluster CA explicitly.
  python3 - "$manifest" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);raw=p.read_text();items=[];decoder=json.JSONDecoder()
while raw.strip():
    raw=raw.lstrip();item,end=decoder.raw_decode(raw);raw=raw[end:]
    items.extend(item['items'] if item['kind']=='List' else [item])
d={'apiVersion':'v1','kind':'List','items':items}
for item in items:
    if item['kind']=='Deployment' and item['metadata']['name']=='metrics-server':
        item['spec']['template']['spec']['containers'][0]['args'].append('--kubelet-certificate-authority=/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
p.write_text(json.dumps(d))
PY
  k apply --server-side -f "$manifest"
fi
k wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=180s
k top nodes
