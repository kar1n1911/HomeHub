# Database HA and credential-isolation verification

> Historical test record. Current deployment is single-node only; any profile/base distinctions below describe the configuration at the time of that test, not current deployment instructions.
The integration run completed on 2026-09-20. Its result and cleanup were rechecked on 2026-09-21 after the interactive session resumed. Machine-readable evidence is in [database-ha.json](database-ha.json).

## Configuration exercised

- OrbStack Kubernetes, one ARM64 node.
- CloudNativePG 1.30.0, two operator replicas.
- PostgreSQL 17.10: one primary, two standbys, separate PVCs, synchronous `ANY 1`, required durability and failover quorum enabled.
- The one-node overlay allowed database Pods to share the host. The multi-node base enforces different nodes and also passed Kubernetes server-side dry-run validation.
- Three separate application databases, non-superuser roles, distinct generated passwords, verified TLS, and two API Pods per service.
- Current source was built as local `homehub-*:ha-test` images. This run did not publish or pull API release `0.1.1` from Docker Hub.

## Observed results

| Check | Result |
| --- | --- |
| Each API connects to its own database | Passed for all three services |
| Verified TLS using cluster CA and Service hostname | Passed |
| Cross-database logins, including maintenance database | Rejected for every application role |
| Attempt to create another database role | Rejected with insufficient privilege |
| Password generation | Three different passwords; rerunning creation preserved existing credentials |
| Primary Pod deletion | Primary changed from `homehub-db-1` to `homehub-db-2` |
| Task committed before failure | Present with the same ID/title after failover |
| New task after failover | Successfully written |
| Time from primary deletion to confirmed API read | 192.4 seconds |
| Replica recovery | Three database instances ready again |
| API continuity | The six API Pod names/UIDs were unchanged |

An API read returned HTTP 500 during the interruption; the test retried the read until it succeeded. Thus the result demonstrates automatic recovery and data retention, not uninterrupted service. In-flight mutations are not automatically retried, because their commit outcome can be uncertain.

The Docker Compose development variant was separately tested: every API became ready, each account accessed only its own database, and foreign-database logins were denied by database CONNECT permissions. Its temporary containers and volume were removed. Compose remains single-instance and does not provide HA.

The original architecture regression suite also passed: eight concurrent initializers per service, atomic rollback, legacy-data adoption, no reseeding after deletion, connection-pool limits, and readiness recovery after a real database stop/start. Python syntax, frontend build, Compose validation, both Kustomize configurations, and diff checks passed.

## Cleanup and limits

The disposable Kubernetes namespace and its PVCs were removed. The original `homehub_homehub-data` volume remains untouched. The two CNPG operator replicas and their CRDs remain installed so the new deployment can be used. Generated local Compose passwords remain under ignored `.secrets/` with restricted permissions.

This one-host run does not prove node or availability-zone outage tolerance, backup recovery, sustained load capacity, or a zero-data-loss guarantee under arbitrary multiple failures. Actual node resilience needs three independently hosted database instances, suitable persistent storage, and an available control plane. The new application databases do not automatically import legacy data.

The application release images still need publication before deploying `0.1.1`. The database and operator currently use official GHCR images. If the coursework requires every infrastructure image to reside on Docker Hub as well as the application images, mirror these pinned upstream images there and update their references before final submission.
