# Cleanup and redeployment regression

> Historical test record. Current deployment is single-node only; any profile/base distinctions below describe the configuration at the time of that test, not current deployment instructions.
Verified 2026-09-22 against local OrbStack (one Ready node, Kubernetes 1.35.6).

## Failure reproduced from the reported workflow

The old README's first deployment block applied the multi-node base. After
cleanup, this replaced the database Cluster's preferred anti-affinity with
required anti-affinity. Existing database Pods could remain running, but the third
instance could not schedule: `didn't match pod anti-affinity rules`.
The Resource Metrics API was absent, and all three CPU HPAs reported
`FailedGetResourceMetric`. KEDA's external metrics provider did not fill this role.

## Changes

- `scripts/deploy-k8s.sh` defaults explicitly to context orbstack, profile local.
  It checks node count and default storage, reuses installed operators, installs
  missing dependencies, retains Secrets, applies the correct overlay and waits
  for the health gate. Multi-node is an explicit profile and refuses fewer than
  three Ready schedulable nodes before any resource changes.
- `scripts/install-metrics-server.sh` pins the official Metrics Server 0.9.0
  manifest for Kubernetes 1.34+. It reuses an existing Metrics API provider.
  The installed collector trusts the cluster CA for kubelet TLS verification;
  no `--kubelet-insecure-tls` argument was added.
- Context is propagated to operator installers and credential creation without
  changing the user's global current-context.
- `scripts/check-k8s-health.py` checks full database readiness, PVC binding,
  application rollout state, actual CPU HPA metrics and KEDA readiness. An idle
  zero-replica worker is valid. Null HPA metrics during startup are handled as a
  waiting state, not a crash or success.
- README and cleanup/video restart instructions use the unified deployment entry.

Official Metrics Server requirements:
https://github.com/kubernetes-sigs/metrics-server#requirements

## Live validation

1. Installed the missing Metrics Server with certificate verification enabled.
2. Reapplied local database affinity; CloudNativePG reconciled the pending Pod
   automatically. Database reached 3/3 without deleting a PVC or Secret.
3. Ran cleanup and redeploy. This exposed a null startup metric handling bug in
   the new health checker; fixed it and added a regression case.
4. Repeated `./scripts/cleanup.sh k8s && ./scripts/deploy-k8s.sh` with the fix.
   The complete command succeeded after application readiness and metrics settled.
5. Observed all six always-on application deployments at 2/2, database 3/3,
   CPU metrics of household 8%, task 10%, device 22% at the final snapshot, and
   a Ready KEDA scaler. Worker was 0/0 after draining work.
6. Compared pre-cleanup task, device and household responses: business data
   unchanged. Device `next_poll` is deliberately excluded because sampling advances
   it normally. All PVC UIDs, Secret UIDs and credential data fingerprints matched.
   No credential values or fingerprints are stored in the evidence file.
7. The page and business APIs were accessible after redeployment. See
   [redeployment-data.json](redeployment-data.json) for preservation checks.

Fresh HPA resources briefly have unknown CPU metrics while collecting samples.
Image pulls may also briefly retry (`pull QPS exceeded` was observed and recovered).
The deployment script waits for health rather than treating apply acceptance as
completion. KEDA's generated HPA may show an unknown metric while its target is
scaled to zero; judge idle state together with ScaledObject readiness and queue
state, not that field alone.

Five isolated health-gate tests passed: healthy idle worker, missing database
replica, null startup CPU metrics, missing worker Deployment, stale rollout.
The multi-node preflight correctly refused the single-node cluster. Shell syntax,
Python compilation, Kustomize render and Git diff checks passed.

This validates redeployment with retained data and existing CNPG/KEDA operators,
plus installation of the previously absent Metrics Server. It does not claim a
new empty cluster install or a multi-node availability test. The unrelated retained
HA test namespace was not deleted or modified.
