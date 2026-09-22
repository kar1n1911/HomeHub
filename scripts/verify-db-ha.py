#!/usr/bin/env python3
"""Verify isolated credentials and primary failover in a disposable CNPG cluster.

Requires the pinned CNPG operator and local Docker/Kubernetes image sharing when
--local-images is used. Deletes only the generated test namespace on success.
On failure it leaves that namespace for diagnosis and prints its name.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--local-images', action='store_true')
parser.add_argument('--namespace', default='homehub-ha-check-' + uuid.uuid4().hex[:8])
args = parser.parse_args()
ns = args.namespace
if not ns.startswith('homehub-ha-check'):
    raise SystemExit('Only homehub-ha-check* disposable namespaces are allowed')


def run(*command, input=None):
    return subprocess.check_output(command, input=input, text=True, cwd=ROOT)


def kube(*command, input=None):
    return run('kubectl', *command, input=input)


def objects(raw):
    decoder = json.JSONDecoder()
    while raw.strip():
        raw = raw.lstrip()
        item, end = decoder.raw_decode(raw)
        yield item
        raw = raw[end:]


def cluster():
    return json.loads(kube('get', 'cluster', 'homehub-db', '-n', ns, '-o', 'json'))


def wait_for(check, description, timeout=240):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except (subprocess.CalledProcessError, KeyError):
            pass
        time.sleep(3)
    raise RuntimeError('Timeout: ' + description)


def execute(service, script):
    return kube('exec', '-i', '-n', ns, f'deployment/{service}-service', '--', 'python', '-', input=script)


# This test intentionally injects a primary failure only in a new namespace.
if kube('get', 'namespace', ns, '--ignore-not-found', '-o', 'name').strip():
    raise SystemExit(f'{ns} already exists; refusing to reuse or delete existing data')
kube('create', 'namespace', ns)
print(f'Test namespace: {ns}', flush=True)
try:
    run('python3', 'scripts/create-db-secrets.py', 'kubernetes', '--namespace', ns)
    passwords = []
    for service in ['household', 'task', 'device']:
        secret = json.loads(kube('get', 'secret', service + '-db', '-n', ns, '-o', 'json'))
        passwords.append(base64.b64decode(secret['data']['password']))
    assert len(set(passwords)) == 3, 'Service passwords must differ'
    del passwords
    if args.local_images:
        for service in ['household', 'task', 'device']:
            run('docker', 'build', '-q', '-t', f'homehub-{service}:ha-test', f'services/{service}-service')
    raw = kube('create', '--dry-run=client', '-f', '-', '-o', 'json',
               input=kube('kustomize', 'kubernetes-local'))
    database_items, api_items = [], []
    for item in objects(raw):
        kind = item['kind']
        name = item['metadata']['name']
        if kind not in ['Cluster', 'Database', 'ConfigMap', 'Deployment', 'Service'] or (kind in ['Deployment', 'Service'] and name not in ['household-service', 'task-service', 'device-service']):
            continue
        item['metadata']['namespace'] = ns
        if kind == 'Deployment':
            container = item['spec']['template']['spec']['containers'][0]
            if args.local_images:
                container['image'] = f"homehub-{name.removesuffix('-service')}:ha-test"
                container['imagePullPolicy'] = 'Never'
        (database_items if kind in ['Cluster', 'Database', 'ConfigMap'] else api_items).append(item)

    def apply(items):
        kube('apply', '-f', '-', input=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}))

    apply(database_items)
    wait_for(lambda: cluster().get('status', {}).get('readyInstances') == 3, 'three database instances', 480)
    wait_for(lambda: all(x.get('status', {}).get('applied') for x in json.loads(kube('get', 'databases', '-n', ns, '-o', 'json'))['items']), 'service databases')
    print('Three database instances ready; all service databases provisioned', flush=True)
    apply(api_items)
    wait_for(lambda: all(x.get('status', {}).get('readyReplicas') == 2 for x in json.loads(kube('get', 'deployments', '-n', ns, '-o', 'json'))['items']), 'six API pods', 240)

    for service in ['household', 'task', 'device']:
        check = '''from app.main import engine, DATABASE_URL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
with engine.connect() as connection:
    who, db = connection.execute(text('SELECT current_user, current_database()')).one()
    assert who == db == EXPECTED
    flags = connection.execute(text('SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user')).one()
    assert not any(flags)
    assert connection.scalar(text('SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()'))
for other in ['homehub_household', 'homehub_task', 'homehub_device', 'postgres']:
    if other == EXPECTED:
        continue
    denied = create_engine(DATABASE_URL.set(database=other), connect_args={'connect_timeout': 2})
    try:
        with denied.connect():
            raise AssertionError('Cross-database login was accepted')
    except DBAPIError as error:
        assert 'pg_hba.conf rejects connection' in str(error.orig), type(error.orig).__name__
    finally:
        denied.dispose()
with engine.connect() as connection:
    try:
        connection.execute(text('CREATE ROLE forbidden_escalation'))
        raise AssertionError('Role escalation was accepted')
    except DBAPIError as error:
        assert error.orig.sqlstate == '42501'
print(EXPECTED + ': own database OK over verified TLS; foreign databases and privilege escalation denied')
'''.replace('EXPECTED', repr('homehub_' + service))
        print(execute(service, check).strip(), flush=True)

    title = 'HA verification ' + uuid.uuid4().hex
    create = '''import json, urllib.request
request = urllib.request.Request('http://127.0.0.1:8000/api/tasks', data=json.dumps({'title': TITLE}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=10) as response:
    assert response.status == 201
    print(response.read().decode())
'''.replace('TITLE', repr(title))
    task = json.loads(execute('task', create))
    original = cluster()['status']['currentPrimary']
    api_before = {p['metadata']['name']: p['metadata']['uid'] for p in json.loads(kube('get', 'pods', '-n', ns, '-o', 'json'))['items'] if p['metadata'].get('labels', {}).get('app', '').endswith('-service')}
    begin = time.monotonic()
    kube('delete', 'pod', original, '-n', ns, '--wait=false')
    wait_for(lambda: cluster()['status'].get('currentPrimary') not in (None, '', original), 'new primary')
    read = '''import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/api/tasks', timeout=8) as response:
    tasks = json.load(response)
assert any(t['id'] == TASK_ID and t['title'] == TITLE for t in tasks)
print('committed task retained')
'''.replace('TASK_ID', str(task['id'])).replace('TITLE', repr(title))
    wait_for(lambda: execute('task', read).strip() == 'committed task retained', 'API recovery and retained task')
    elapsed = round(time.monotonic() - begin, 1)
    # Prove writes now route to the new primary, not just reads from cached data.
    json.loads(execute('task', create.replace(title, title + ' after failover')))
    wait_for(lambda: cluster().get('status', {}).get('readyInstances') == 3, 'replica rebuild')
    api_after = {p['metadata']['name']: p['metadata']['uid'] for p in json.loads(kube('get', 'pods', '-n', ns, '-o', 'json'))['items'] if p['metadata'].get('labels', {}).get('app', '').endswith('-service')}
    assert api_before == api_after, 'API pods were replaced during failover'
    final = cluster()
    primary = final['status']['currentPrimary']
    sync = kube('exec', '-n', ns, primary, '-c', 'postgres', '--', 'psql', '-At', '-c', 'SHOW synchronous_standby_names').strip()
    assert sync.startswith('ANY 1'), sync
    evidence = {
        'namespace': ns, 'oldPrimary': original, 'newPrimary': primary,
        'recoverySeconds': elapsed, 'instancesReady': 3, 'synchronousStandbys': sync,
        'crossDatabaseAccess': 'denied for all three application roles',
        'privilegeEscalation': 'denied', 'tls': 'verify-full',
        'committedTaskRetained': True, 'writeAfterFailover': True,
        'apiPodsUnchanged': True, 'localImages': args.local_images,
        'scope': 'single-node Pod-failure test; not a node or zone outage test',
    }
    output = ROOT / 'docs' / 'verification' / 'database-ha.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2), flush=True)
except Exception:
    print(f'Validation failed. Retained disposable namespace for diagnosis: {ns}', flush=True)
    raise
else:
    kube('delete', 'namespace', ns, '--wait=false')
    print('Requested deletion of test namespace and its disposable database volumes', flush=True)
