"""Exercise transient/redeployment states without touching a cluster."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/check-k8s-health.py'

class HealthGateTests(unittest.TestCase):
    def fixture(self):
        condition = lambda name: {'type': name, 'status': 'True'}
        apps = ['frontend', 'household-service', 'task-service', 'device-service', 'alertmanager', 'signal-receiver', 'signal-worker']
        deploys = []
        for name in apps:
            n = 0 if name == 'signal-worker' else 2
            deploys.append({'metadata': {'name': name, 'generation': 1}, 'spec': {'replicas': n}, 'status': {'readyReplicas': n, 'updatedReplicas': n, 'observedGeneration': 1}})
        return {
            'clusters.postgresql.cnpg.io': {'spec': {'instances': 3}, 'status': {'readyInstances': 3, 'conditions': [condition('Ready')]}},
            'deployments': {'items': deploys},
            'pvc': {'items': [{'metadata': {'labels': {'cnpg.io/cluster': 'homehub-db'}}, 'status': {'phase': 'Bound'}} for _ in range(3)]},
            'apiservices.apiregistration.k8s.io': {'status': {'conditions': [condition('Available')]}},
            'hpa': {'items': [{'metadata': {'name': name}, 'status': {'conditions': [condition('ScalingActive')], 'currentMetrics': [{'resource': {'current': {'averageUtilization': 12}}}]}} for name in apps[1:4]]},
            'scaledobjects': {'status': {'conditions': [condition('Ready')]}}
        }

    def run_gate(self, data):
        def output(cmd, **kwargs):
            self.assertIn('orbstack', cmd)
            return json.dumps(data[cmd[cmd.index('get') + 1]])
        with patch.object(sys, 'argv', [str(SCRIPT)]), patch('subprocess.check_output', side_effect=output), contextlib.redirect_stdout(io.StringIO()):
            try:
                runpy.run_path(str(SCRIPT), run_name='__main__')
            except SystemExit as exc:
                return exc.code
        return 0

    def test_idle_worker_is_healthy(self):
        self.assertEqual(self.run_gate(self.fixture()), 0)

    def test_database_missing_replica_fails(self):
        data = self.fixture(); data['clusters.postgresql.cnpg.io']['status']['readyInstances'] = 2
        self.assertEqual(self.run_gate(data), 1)

    def test_initial_null_hpa_metrics_fail_cleanly(self):
        data = self.fixture(); data['hpa']['items'][0]['status']['currentMetrics'] = None
        self.assertEqual(self.run_gate(data), 1)

    def test_missing_worker_deployment_fails(self):
        data = self.fixture(); data['deployments']['items'].pop()
        self.assertEqual(self.run_gate(data), 1)

    def test_outdated_rollout_fails(self):
        data = self.fixture(); data['deployments']['items'][0]['status']['observedGeneration'] = 0
        self.assertEqual(self.run_gate(data), 1)

if __name__ == '__main__':
    unittest.main()
