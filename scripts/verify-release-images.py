#!/usr/bin/env python3
"""Read-only verification of the published release and current HomeHub Pods."""
import concurrent.futures
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.check_output(args,text=True)

def inspect(service):
    version='0.2.2' if service=='frontend' else '0.2.0'
    reference=f'kar1n1911/homehub-{service}:{version}'
    raw=json.loads(run('docker','buildx','imagetools','inspect','--raw',reference))
    platforms=sorted({m['platform']['os']+'/'+m['platform']['architecture'] for m in raw['manifests'] if m['platform']['os']=='linux'})
    assert platforms==['linux/amd64','linux/arm64'],reference
    summary=run('docker','buildx','imagetools','inspect',reference)
    digest=next(line.split()[1] for line in summary.splitlines() if line.startswith('Digest:'))
    return {'image':reference,'digest':digest,'platforms':platforms}

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    manifests=list(pool.map(inspect,['frontend','household','task','device','alertmanager']))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
(ROOT/'docs/verification/release-images.json').write_text(json.dumps({'checked_at':now,'images':manifests},indent=2)+'\n')
source_checks=[]
for deployment,directory in [('household-service','household-service'),('task-service','task-service'),('device-service','device-service'),('alertmanager','alertmanager-service')]:
    local=hashlib.sha256((ROOT/'services'/directory/'app/main.py').read_bytes()).hexdigest()
    remote=run('kubectl','-n','homehub','exec','deployment/'+deployment,'--','sha256sum','/app/app/main.py').split()[0]
    assert local==remote,deployment
    source_checks.append({'deployment':deployment,'source_sha256':local,'matches_workspace':True})
pods=json.loads(run('kubectl','-n','homehub','get','pods','-o','json'))['items']
records=[]
for pod in pods:
    if pod['metadata'].get('deletionTimestamp'):
        continue
    for container in pod.get('status',{}).get('containerStatuses',[]):
        if not container['image'].startswith('kar1n1911/'):
            continue
        assert container['image'] in {m['image'] for m in manifests} and container['ready'],pod['metadata']['name']
        spec=next(c for c in pod['spec']['containers'] if c['name']==container['name'])
        assert spec['imagePullPolicy']=='Always'
        records.append({'pod':pod['metadata']['name'],'deployment':pod['metadata']['labels']['app'],'image':container['image'],'image_id':container['imageID'],'ready':True})
for deployment in ['frontend','household-service','task-service','device-service','alertmanager','signal-receiver']:
    assert sum(r['deployment']==deployment for r in records)>=2,deployment
report={'checked_at':now,'context':run('kubectl','config','current-context').strip(),'image_pull_policy':'Always','pods':records,'source_checks':source_checks}
(ROOT/'docs/verification/release-node-pull.json').write_text(json.dumps(report,indent=2)+'\n')
print('Five dual-architecture registry images verified; six deployments ready; backend source matches workspace.')
