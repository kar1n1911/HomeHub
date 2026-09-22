# HomeHub architecture

## Components and request flow

The React frontend is served by Nginx, which routes `/api/households`, `/api/tasks`, `/api/devices`, and `/api/signals` to separate Kubernetes Services. Each stateless FastAPI service has its own Deployment; the original APIs use CPU HPA, while signal workers use queue-based KEDA scaling. Household owns member data, Task owns task CRUD, and Device owns simulated device state.

Each API authenticates with its own non-superuser PostgreSQL role and owns a separate database. All five service databases are replicated by one CloudNativePG cluster with three PostgreSQL instances. API connections use `homehub-db-rw`, whose endpoint follows the writable primary. Each database instance has its own PVC; replicas do not share a data directory.

| API | Database / role | Kubernetes Secret | Owned tables |
| --- | --- | --- | --- |
| Household | `homehub_household` | `household-db` | `household_members`, `household_initialization` |
| Task | `homehub_task` | `task-db` | `tasks`, `task_initialization` |
| Device | `homehub_device` | `device-db` | `devices`, `device_initialization`, `device_sampling`, `device_signals` |
| Alertmanager collector/worker | `homehub_alertmanager` | `alertmanager-db` | `signal_messages` |
| Local HTTP receiver | `homehub_receiver` | `receiver-db` | `signal_messages` |

There are no cross-database joins. The frontend aggregates REST responses; Alertmanager collectors claim device outbox messages over authenticated HTTP, persist them in their own queue, and workers transmit JSON to the separately credentialed receiver. No service bypasses another service's database ownership.

## Database availability

CloudNativePG 1.30.0 manages a primary and two standbys, automatic primary election, replication, and the read/write Service. We pin the PostgreSQL 17.10 image by digest. Synchronous replication requires acknowledgement from one standby (`ANY 1`), and `failoverQuorum` adds a quorum check before promotion. A successful ordinary commit therefore waits for replication; a lost client connection during commit still has an uncertain outcome and must not be blindly retried as a new task creation.

The supported `kubernetes/` deployment runs on one OrbStack node, with preferred database anti-affinity so all three instances can schedule on that node. `kubernetes-local/` is only a compatibility alias. Three database instances allow process-level failover, but share the host, storage and control plane. Application replica scaling uses the same finite host resources and does not provide host-level fault tolerance.

The design tolerates a single database-instance failure while a usable standby quorum remains. Failover causes an interruption, not zero downtime. The recorded local primary-Pod-deletion test took 192.4 seconds from deletion to successful API read; this includes graceful termination, promotion, reconnection, and polling and is not a guaranteed recovery SLA. If both standbys are unavailable, required synchronous replication pauses commits rather than silently falling back to unreplicated writes. API requests can time out during an outage. All services still share database-cluster capacity and this failure domain; separate databases provide access isolation, not independent compute.

The operator installation script runs two operator replicas with leader election and preferred separation across nodes. This reduces operator-process dependence but does not create a highly available Kubernetes control plane. Replication and PVCs are not backups: accidental deletion and bad writes replicate too. Off-cluster backups and restore drills remain necessary for production and are not configured here.

## Credential isolation and transport

`scripts/create-db-secrets.py kubernetes` creates a different random password for each service directly in Kubernetes, without writing secrets to source files or printing their values. Existing secrets are retained on repeat runs. Each API receives only its own username/password; the old shared `homehub-secrets` resource and hard-coded superuser fallback are removed. API pods do not mount Kubernetes service-account tokens.

Roles cannot create databases or roles, bypass row security, replicate, or become superusers. Ordered `pg_hba` rules allow each application role to connect only to its own database over TLS, rejecting all its other database connections before the default rules. This is a server-enforced access boundary even though PostgreSQL's default database CONNECT grants exist. PostgreSQL is not externally exposed.

API connections use `sslmode=verify-full` and mount only `ca.crt` from the operator-generated CA Secret, checking both trust and the read/write Service hostname. The CA private key is not mounted into API pods. Application roles own their own databases so they can create their own tables at startup; separating migration and runtime roles would further reduce privileges within each database.

Kubernetes Secrets require proper cluster RBAC and encryption-at-rest configuration. This change does not add end-user login, HTTP TLS ingress, or NetworkPolicies. Database isolation prevents one service credential from directly accessing another database, but does not protect unauthenticated public APIs. Password rotation must update the specific basic-auth Secret, wait for the operator to reconcile that role, and restart only the affected API Deployment to refresh its environment. Other services' credentials do not need to change.

## Concurrent initialization

The original APIs use distinct PostgreSQL transaction advisory locks (71001 household, 71002 task, 71003 device). Signal service roles use lock 71004 in their own database for table initialization. Table creation, seed insertion, and a service-specific initialization marker commit in one transaction. Concurrent replicas serialize initialization; failure rolls everything back.

An existing nonempty table is adopted without adding sample rows. After its marker exists, deleting every row does not cause samples to return on restart. An empty legacy table without a marker is indistinguishable from a fresh installation and receives seed data once. These markers are not a schema migration framework; future column changes need explicit migrations.

## Health and connection budget

`/health` checks process liveness independently of PostgreSQL. `/ready` queries the API's own business table and returns 503 for missing tables, database errors, or pool exhaustion. Startup probes allow initialization before liveness starts. Existing pooled connections are checked before reuse, allowing APIs to reconnect after a primary change. Failed in-flight writes are not automatically replayed.

Each API process has two pooled connections, zero overflow, a two-second pool wait, a two-second connection timeout, and a two-second statement timeout. At HPA maxima of 6/8/10 pods, steady-state API connections total at most 48. Default rolling surges may add seven non-terminating pods (14 more connections). Terminating pods, operator work, monitoring, and administration need additional headroom below PostgreSQL's configured 100 connections. Per-role limits of 20/24/28 further bound each service. The signal collector, workers and receiver add up to 16 steady-state connections and up to six additional connections during rollout, giving 64 steady-state and 84 including non-terminating surge Pods. Their role limits are 16 and 8. Recalculate budgets when changing replica or worker counts; test under load before increasing limits.

## Development and migration

Compose remains a lightweight single-instance development option, not an HA deployment. It uses the same five separate databases/roles, generated password files under ignored `.secrets/`, and SQL CONNECT grants to deny cross-database logins. The admin password is available only to the database container. Its private development network uses plaintext PostgreSQL; Kubernetes uses verified TLS.

The new Compose volume is `homehub-isolated-data`. The legacy `homehub-data` volume is deliberately not mounted, modified, or deleted. The Kubernetes cluster also creates new PVCs rather than reusing a single-instance data directory. Existing data is not automatically migrated. Before a real upgrade, stop writes, back up the old database, export each service's tables and sequences, restore them to the matching new database under its owner, validate row counts and sequence values, and only then start the APIs. Retain the old backup until acceptance. Restoring populated tables before startup lets the initialization code adopt them without duplicating data; preserve initialization markers for intentionally empty tables.

## Cost and business tradeoffs

Three PostgreSQL instances, storage copies, synchronous replication traffic, and an operator cost more than the previous single database. Synchronous commits add latency and strict durability can reduce write availability during multiple failures. In exchange, a single PostgreSQL instance failure no longer requires waiting for that same instance to restart, and leaked service credentials have a smaller data-access scope.

A single household rarely justifies this architecture. The coursework scenario assumes many households and unequal API traffic, motivating independent API scaling and reliable shared state. The current application still models one household with simulated devices; multi-tenant authorization is not implemented.

## Verification and sources

Run `python3 scripts/verify-db-ha.py --local-images` on OrbStack to build current APIs and test a disposable Kubernetes cluster. It checks six API pods, verified TLS, denied cross-database access and role escalation, committed task retention across primary Pod deletion, a subsequent write, and API Pod continuity. It deletes its test namespace on success and leaves failed runs for diagnosis. This is a destructive test only inside its newly created `homehub-ha-check-*` namespace.

The release manifests use application images `0.2.0`. Local-image verification alone does not establish publication; consult the separate signal/image verification records for registry and node-pull evidence.

- [Operator installation](https://cloudnative-pg.io/docs/1.30/installation_upgrade/)
- [Replication and durability](https://cloudnative-pg.io/docs/1.30/replication/)
- [Role management](https://cloudnative-pg.io/docs/1.30/declarative_role_management/)
- [Database management](https://cloudnative-pg.io/docs/1.30/declarative_database_management/)
- [Instance scheduling](https://cloudnative-pg.io/docs/1.30/scheduling/)

## Device signal extension (0.2.0)

The device API now supports registration, staggered persisted schedules, and a transactional outbox. Alertmanager collectors, independently scaled delivery workers, and a separately credentialed HTTP receiver implement durable JSON delivery. The updated component mapping, scaling behavior, security limitations, and migration commands are described in [device-signals.md](device-signals.md).
