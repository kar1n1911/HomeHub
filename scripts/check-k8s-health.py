#!/usr/bin/env python3
"""Read-only health gate: do not equate kubectl apply success with readiness."""
import argparse
import json
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--context', default='orbstack')
parser.add_argument('--timeout', type=int, default=0, help='Seconds to wait; default checks once')
args = parser.parse_args()
base = ['kubectl', '--context', args.context, '--request-timeout=15s']
apps = ['frontend', 'household-service', 'task-service', 'device-service', 'alertmanager', 'signal-receiver']

def get(kind, name=None, namespace='homehub'):
    cmd = base + (['-n', namespace] if namespace else []) + ['get', kind]
    if name:
        cmd.append(name)
    return json.loads(subprocess.check_output(cmd + ['-o', 'json'], text=True, stderr=subprocess.PIPE))

def true_condition(obj, name):
    return any(c['type'] == name and c['status'] == 'True' for c in (obj.get('status', {}).get('conditions') or []))

def check():
    issues = []
    cluster = get('clusters.postgresql.cnpg.io', 'homehub-db')
    if cluster['status'].get('readyInstances', 0) != cluster['spec']['instances'] or not true_condition(cluster, 'Ready'):
        issues.append(f"Database ready {cluster['status'].get('readyInstances', 0)}/{cluster['spec']['instances']}")
    deployments = {d['metadata']['name']: d for d in get('deployments')['items']}
    for name in [*apps, 'signal-worker']:
        d = deployments.get(name, {})
        wanted = d.get('spec', {}).get('replicas', 0)
        status = d.get('status', {})
        if not d or wanted < (0 if name == 'signal-worker' else 1) or status.get('readyReplicas', 0) != wanted or status.get('updatedReplicas', 0) != wanted or status.get('observedGeneration', 0) < d.get('metadata', {}).get('generation', 1):
            issues.append(f'{name} rollout not ready')
    volumes = get('pvc')['items']
    db_volumes = [v for v in volumes if v['metadata'].get('labels', {}).get('cnpg.io/cluster') == 'homehub-db']
    if len(db_volumes) < cluster['spec']['instances'] or any(v.get('status', {}).get('phase') != 'Bound' for v in db_volumes):
        issues.append('Database PVCs not all Bound')
    metrics = get('apiservices.apiregistration.k8s.io', 'v1beta1.metrics.k8s.io', namespace=None)
    if not true_condition(metrics, 'Available'):
        issues.append('Resource Metrics API unavailable')
    hpas = {h['metadata']['name']: h for h in get('hpa')['items']}
    for name in ['household-service', 'task-service', 'device-service']:
        h = hpas.get(name, {})
        cpu = any(m.get('resource', {}).get('current', {}).get('averageUtilization') is not None for m in (h.get('status', {}).get('currentMetrics') or []))
        if not true_condition(h, 'ScalingActive') or not cpu:
            issues.append(f'{name} CPU HPA has no usable metric')
    if not true_condition(get('scaledobjects', 'signal-worker'), 'Ready'):
        issues.append('KEDA signal-worker scaler not ready')
    return issues

end = time.monotonic() + max(0, args.timeout)
previous = None
while True:
    try:
        issues = check()
    except (subprocess.CalledProcessError, KeyError, ValueError) as exc:
        issues = [f'Health query failed: {type(exc).__name__}']
    if not issues:
        print('Healthy: database fully ready; PVCs Bound; application rollouts ready; CPU HPA metrics available; KEDA ready (idle worker may be zero).')
        break
    message = '; '.join(issues)
    if message != previous:
        print(message, flush=True)
        previous = message
    if time.monotonic() >= end:
        raise SystemExit(1)
    time.sleep(min(10, max(0, end - time.monotonic())))
