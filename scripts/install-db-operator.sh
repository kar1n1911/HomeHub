#!/usr/bin/env sh
set -eu
# Render the pinned release before applying so repeated installs retain two replicas.
raw_manifest=$(mktemp)
ha_manifest=$(mktemp)
trap 'rm -f "$raw_manifest" "$ha_manifest"' EXIT
kubectl create --dry-run=client --validate=false \
  -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/v1.30.0/releases/cnpg-1.30.0.yaml \
  -o json > "$raw_manifest"
python3 - "$raw_manifest" "$ha_manifest" <<'PY'
import json
from pathlib import Path
import sys
raw = Path(sys.argv[1]).read_text()
decoder = json.JSONDecoder()
items = []
while raw.strip():
    raw = raw.lstrip()
    item, end = decoder.raw_decode(raw)
    raw = raw[end:]
    if item['kind'] == 'Deployment' and item['metadata']['name'] == 'cnpg-controller-manager':
        item['spec']['replicas'] = 2
        item['spec']['template']['spec']['affinity'] = {
            'podAntiAffinity': {'preferredDuringSchedulingIgnoredDuringExecution': [{
                'weight': 100,
                'podAffinityTerm': {
                    'labelSelector': {'matchLabels': {'app.kubernetes.io/name': 'cloudnative-pg'}},
                    'topologyKey': 'kubernetes.io/hostname',
                },
            }]},
        }
    items.append(item)
Path(sys.argv[2]).write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}))
PY
kubectl apply --server-side -f "$ha_manifest"
kubectl rollout status deployment/cnpg-controller-manager -n cnpg-system --timeout=180s
