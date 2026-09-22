#!/usr/bin/env python3
"""Exercise the running Compose demo without deleting existing household data."""
import json
import subprocess
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def compose(*args, capture=False):
    return subprocess.run(['docker', 'compose', *args], check=True, text=True, capture_output=capture)


def api(path, data=None):
    with urlopen(Request('http://localhost:8080' + path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'}), timeout=10) as response:
        return json.load(response)


def sql(db, query):
    return compose('exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', db, '-Atc', query, capture=True).stdout.strip()


def eventually(check, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (HTTPError, URLError):
            pass
        time.sleep(1)
    raise AssertionError('Condition did not converge')


def main():
    eventually(lambda: bool(api('/api/devices')))
    device = api('/api/devices', {'name': 'Delivery recovery verification', 'room': 'Test bench', 'value': 'ready', 'poll_interval_seconds': 3600})
    identity = str(uuid.uuid4())
    payload = {'message_id': identity, 'value': '23.5 C', 'online': True}
    compose('stop', 'signal-receiver')
    try:
        assert api(f"/api/devices/{device['id']}/signals", payload)['duplicate'] is False
        assert api(f"/api/devices/{device['id']}/signals", payload)['duplicate'] is True
        try:
            api(f"/api/devices/{device['id']}/signals", {**payload, 'value': 'conflict'})
            raise AssertionError('Conflicting ID accepted')
        except HTTPError as exc:
            assert exc.code == 409
        eventually(lambda: sql('homehub_alertmanager', f"SELECT count(*) FROM signal_messages WHERE id='{identity}' AND attempts > 0 AND delivered_at IS NULL") == '1')
        # A process restart must not remove the queue or its retry state.
        compose('restart', 'alertmanager', 'signal-worker', 'device-service')
        assert sql('homehub_alertmanager', f"SELECT count(*) FROM signal_messages WHERE id='{identity}' AND delivered_at IS NULL") == '1'
    finally:
        compose('start', 'signal-receiver')
    compose('up', '-d', '--no-build', '--scale', 'signal-worker=2', 'signal-worker')
    eventually(lambda: sql('homehub_alertmanager', f"SELECT count(*) FROM signal_messages WHERE id='{identity}' AND delivered_at IS NOT NULL") == '1')
    assert sql('homehub_receiver', f"SELECT count(*) FROM signal_messages WHERE id='{identity}'") == '1'
    # Simulate lost acknowledgement AFTER the receiver commits: redeliver same ID.
    sql('homehub_alertmanager', f"UPDATE signal_messages SET delivered_at=NULL,next_attempt=now() WHERE id='{identity}'")
    eventually(lambda: sql('homehub_alertmanager', f"SELECT count(*) FROM signal_messages WHERE id='{identity}' AND delivered_at IS NOT NULL") == '1')
    assert sql('homehub_receiver', f"SELECT count(*) FROM signal_messages WHERE id='{identity}'") == '1'
    eventually(lambda: next(d for d in api('/api/devices') if d['id'] == device['id'])['value'] == '23.5 C')
    # A worker killed after claiming cannot permanently strand its message.
    sql('homehub_alertmanager', f"UPDATE signal_messages SET delivered_at=NULL,next_attempt=now(),lease='{uuid.uuid4()}',lease_until=now()+interval '3 seconds' WHERE id='{identity}'")
    eventually(lambda: sql('homehub_alertmanager', f"SELECT count(*) FROM signal_messages WHERE id='{identity}' AND delivered_at IS NOT NULL") == '1')
    assert sql('homehub_receiver', f"SELECT count(*) FROM signal_messages WHERE id='{identity}'") == '1'
    # An unchanged due sample does not produce redundant data.
    before = sql('homehub_device', f"SELECT count(*) FROM device_signals WHERE device_id={device['id']}")
    sql('homehub_device', f"UPDATE device_sampling SET next_poll=now() WHERE device_id={device['id']}")
    eventually(lambda: sql('homehub_device', f"SELECT count(*) FROM device_sampling WHERE device_id={device['id']} AND next_poll>now()") == '1')
    assert sql('homehub_device', f"SELECT count(*) FROM device_signals WHERE device_id={device['id']}") == before
    sql('homehub_device', f"UPDATE device_sampling SET next_poll=now(),last_emit=now()-interval '301 seconds' WHERE device_id={device['id']}")
    eventually(lambda: int(sql('homehub_device', f"SELECT count(*) FROM device_signals WHERE device_id={device['id']}")) == int(before)+1)
    compose('up', '-d', '--no-build', '--scale', 'signal-worker=1', 'signal-worker')
    print(json.dumps({'result': 'passed', 'device_id': device['id'], 'message_id': identity, 'checks': ['source idempotency', 'conflicting ID rejected', 'receiver outage retry', 'process restart durability', 'two concurrent workers', 'receiver duplicate suppression after lost acknowledgement', 'device state persisted', 'expired worker lease reclaimed', 'unchanged polling suppressed', 'heartbeat emitted on next due poll']}, indent=2))

if __name__ == '__main__':
    main()
