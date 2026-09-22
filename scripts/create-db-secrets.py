#!/usr/bin/env python3
"""Create unique service passwords without printing them or putting them in Git."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('target', choices=['kubernetes', 'compose'])
parser.add_argument('--namespace', default='homehub')
args = parser.parse_args()
services = ['household', 'task', 'device', 'alertmanager', 'receiver']
if args.target == 'compose':
    directory = Path(__file__).resolve().parents[1] / '.secrets'
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    for service in ['admin', 'pipeline', *services]:
        path = directory / f'{service}-password'
        if path.exists():
            if not path.read_text().strip():
                raise SystemExit(f'Empty password file: {path.name}')
            path.chmod(0o600)
            continue
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(secrets.token_urlsafe(48) + '\n')
    print('Local secret files ready; existing passwords retained.')
else:
    subprocess.run(['kubectl', 'get', 'namespace', args.namespace], check=True, stdout=subprocess.DEVNULL)
    for service in services:
        name = f'{service}-db'
        existing = subprocess.check_output([
            'kubectl', 'get', 'secret', name, '-n', args.namespace,
            '--ignore-not-found', '-o', 'json'], text=True)
        if existing.strip():
            data = json.loads(existing)['data']
            if base64.b64decode(data['username']).decode() != f'homehub_{service}' or not base64.b64decode(data['password']):
                raise SystemExit(f'Existing {name} has unexpected or empty credentials; not overwritten.')
            continue
        secret = {
            'apiVersion': 'v1', 'kind': 'Secret',
            'metadata': {'name': name, 'namespace': args.namespace,
                         'labels': {'cnpg.io/reload': 'true'}},
            'type': 'kubernetes.io/basic-auth',
            'stringData': {'username': f'homehub_{service}', 'password': secrets.token_urlsafe(48)},
        }
        result = subprocess.run(['kubectl', 'create', '-f', '-'], input=json.dumps(secret),
                                text=True, capture_output=True)
        if result.returncode:
            # Never echo the serialized secret or kubectl's request error body.
            raise SystemExit(f'Could not create {name}; inspect Kubernetes permissions and retry.')
    print(f'Database Secrets ready in {args.namespace}; existing passwords retained.')

if args.target == 'kubernetes':
    existing = subprocess.check_output(['kubectl', 'get', 'secret', 'signal-pipeline', '-n', args.namespace, '--ignore-not-found', '-o', 'name'], text=True)
    if not existing.strip():
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'signal-pipeline', 'namespace': args.namespace}, 'stringData': {'token': secrets.token_urlsafe(48)}}
        result = subprocess.run(['kubectl', 'create', '-f', '-'], input=json.dumps(secret), text=True, capture_output=True)
        if result.returncode:
            raise SystemExit('Could not create pipeline Secret')
