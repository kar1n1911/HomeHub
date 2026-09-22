"""Run real HTTP checks while stopping/restarting the disposable test database."""
import json
from pathlib import Path
import subprocess
import sys
import time

network, database = sys.argv[1:]
if not network.startswith('homehub-architecture-') or database != network + '-db':
    raise SystemExit('Only disposable architecture-test resources are allowed')
root = Path(__file__).resolve().parents[1]
containers = []


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def statuses(container):
    script = '''import json, urllib.request, urllib.error
result = {}
for path in ['/health', '/ready']:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=8) as response:
            result[path] = response.status
    except urllib.error.HTTPError as error:
        result[path] = error.code
    except (urllib.error.URLError, TimeoutError):
        result[path] = 0
print(json.dumps(result))'''
    return json.loads(docker('exec', container, 'python', '-c', script))


def wait_ready():
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if all(statuses(name) == {'/health': 200, '/ready': 200} for name in containers):
            return
        time.sleep(1)
    raise AssertionError('Services did not become ready')


try:
    starts = {}
    for service in ['household', 'task', 'device']:
        name = network + '-' + service
        docker('run', '-d', '--name', name, '--network', network,
               '-e', f'DATABASE_URL=postgresql+psycopg://homehub:test_only@{database}:5432/homehub_test',
               '-v', f'{root}/services/{service}-service/app:/app/app:ro',
               'homehub-architecture-test:local')
        containers.append(name)
        starts[name] = docker('inspect', '--format', '{{.State.StartedAt}}', name)
    wait_ready()
    docker('stop', '--time', '5', database)
    for name in containers:
        assert statuses(name) == {'/health': 200, '/ready': 503}, name
    print('Database stopped: all three real HTTP servers return health=200, ready=503')
    docker('start', database)
    wait_ready()
    for name in containers:
        assert docker('inspect', '--format', '{{.State.StartedAt}}', name) == starts[name], name
    print('Database recovered: all three return ready=200 without API container restarts')
except Exception:
    for name in containers:
        print(docker('logs', '--tail', '30', name))
    raise
finally:
    for name in containers:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, check=False)
