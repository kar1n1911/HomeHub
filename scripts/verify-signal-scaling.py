#!/usr/bin/env python3
"""Fault-injection verification on the local HomeHub Kubernetes demo.
Temporarily stops only signal-receiver, restores its original replica count,
and leaves the created test device/readings as visible verification evidence.
"""
import json
import subprocess
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

NS = 'homehub'
BASE = 'http://localhost:30080'

def kube(*args):
    return subprocess.check_output(['kubectl', '-n', NS, *args], text=True)

def deployment(name):
    return json.loads(kube('get', 'deployment', name, '-o', 'json'))

def api(path, data=None):
    with urlopen(Request(BASE + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type':'application/json'}), timeout=10) as response:
        return json.load(response)

def wait(check, label, timeout=240):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            result=check()
            if result:
                print(label, flush=True)
                return result
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('Timed out: '+label)

wait(lambda: api('/api/signals/stats')['depth']==0, 'Initial queue drained')
wait(lambda: deployment('signal-worker')['spec']['replicas']==0, 'Idle workers scaled to zero')
receiver_replicas=deployment('signal-receiver')['spec']['replicas']
identities=[]
try:
    kube('scale','deployment/signal-receiver','--replicas=0')
    wait(lambda: not json.loads(kube('get','pods','-l','app=signal-receiver','-o','json'))['items'], 'Receiver stopped')
    device=api('/api/devices',{'name':'Kubernetes scaling verification','room':'Test bench','value':'ready','poll_interval_seconds':3600})
    for i in range(45):
        identity=str(uuid.uuid4());identities.append(identity)
        api(f"/api/devices/{device['id']}/signals", {'message_id':identity,'value':f'reading {i}','online':True})
    wait(lambda: api('/api/signals/stats')['depth']>=45, 'At least 45 signals durably queued')
    workers=wait(lambda: deployment('signal-worker').get('status',{}).get('readyReplicas',0)>=2, 'Queue caused multiple worker replicas')
    peak=deployment('signal-worker')['spec']['replicas']
    worker_pods=json.loads(kube('get','pods','-l','app=signal-worker','-o','json'))['items']
    worker_images=sorted({c['imageID'] for pod in worker_pods for c in pod.get('status',{}).get('containerStatuses',[]) if c.get('imageID')})
    # Kill active workers; leases and records must survive replacement.
    kube('delete','pods','-l','app=signal-worker','--wait=false')
    wait(lambda: deployment('signal-worker').get('status',{}).get('readyReplicas',0)>=2, 'Worker pods replaced')
finally:
    kube('scale','deployment/signal-receiver',f'--replicas={receiver_replicas}')
wait(lambda: api('/api/signals/stats')['depth']==0, 'Queue drained after receiver recovery')
# Inspect receiver-owned storage through its own container, without printing credentials.
code='''import json
from app.main import engine, Message
from sqlalchemy import select
with engine.connect() as c:
 print(json.dumps(list(c.scalars(select(Message.id)))))
'''
received=json.loads(kube('exec','deployment/signal-receiver','--','python','-c',code))
assert set(identities).issubset(set(received))
assert len(received)==len(set(received))
wait(lambda: deployment('signal-worker')['spec']['replicas']==0, 'Workers returned to zero')
report={'result':'passed','context':subprocess.check_output(['kubectl','config','current-context'],text=True).strip(),'signals':len(identities),'peak_worker_replicas':peak,'final_worker_replicas':0,'worker_image_ids':worker_images,'all_test_ids_received':True,'checks':['zero-to-many activation','receiver outage persistence','worker pod replacement','all messages recovered','receiver unique IDs','idle scale-to-zero']}
Path('docs/verification/signal-scaling.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
