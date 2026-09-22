# HomeHub

HomeHub is a microservice-based household management application for Kubernetes coursework. A React interface displays household members, shared tasks, and simulated smart devices. FastAPI services provide household, task, device, and durable signal-delivery REST APIs. The browser supports task completion and device registration.

## Architecture

```text
Browser -> React / Nginx (NodePort 30080)
                  |
       +----------+-----------+
       |          |           |
   Household     Task       Device      independently scalable APIs
       |          |           |
   household     task       device      separate DBs, roles, passwords
       +----------+-----------+
                  |
        homehub-db-rw Service
                  |
   PostgreSQL primary -> two standbys   CloudNativePG; synchronous replication
       PVC               PVC + PVC
```

Device signals additionally flow through a durable outbox → Alertmanager queue → local HTTP receiver. KEDA scales sending workers from zero to four independently of collection. See [device signal design and failure boundaries](docs/architecture/device-signals.md).

Each service has its own database and restricted credential. Kubernetes runs three PostgreSQL instances with automatic failover. The default deployment requires different nodes for database instances. The local overlay supports a one-node demonstration and does not protect against loss of the host.

## Local development with Compose

Requirements: Docker with Compose and Python 3.

```bash
python3 scripts/create-db-secrets.py compose
docker compose up --build
```

Open <http://localhost:8080>. Password files are generated under ignored `.secrets/` and existing passwords are retained. Each API receives only its own password. Compose uses a single database instance for development; HA is implemented in Kubernetes.

```bash
docker compose down
```

This retains the new `homehub-isolated-data` database volume. The old `homehub-data` volume is not mounted or deleted. The new databases start fresh unless you explicitly migrate data; see the architecture document. Do not delete password files while retaining their database volume, as newly generated passwords will not match the stored roles. `docker compose down -v` deletes the current development database and should only be used deliberately.

## REST APIs

| Service | Method | Endpoint | Purpose |
|---|---|---|---|
| Household | GET | `/api/households` | Household and member summary |
| Household | GET | `/api/households/members` | List members |
| Task | GET | `/api/tasks` | List tasks |
| Task | POST | `/api/tasks` | Create task |
| Task | PATCH | `/api/tasks/{id}` | Update task |
| Task | DELETE | `/api/tasks/{id}` | Delete task |
| Device | GET | `/api/devices` | List simulated devices |
| Device | POST | `/api/devices` | Add a device and sampling schedule |
| Device | POST | `/api/devices/{id}/signals` | Idempotently submit a reading with its UUID |
| Alertmanager | GET | `/api/signals/stats` | Delivery state and recent JSON messages |
| Device | PATCH | `/api/devices/{id}` | Update simulated device state |

Every API exposes `/health` for liveness and `/ready` for database-backed readiness. The frontend supports creating tasks (name, optional due date, priority), marking them complete/incomplete, and reloading their persisted state from the API. The device panel adds simulated devices, selects sampling intervals, and shows JSON delivery status. Task editing/deletion forms and device editing controls are not wired into the UI yet.

## Build and publish application images

The application manifests use release `0.2.0` under `kar1n1911` on Docker Hub. Five images cover frontend, household, task, device, and Alertmanager; collector, worker and receiver use the same Alertmanager image with separate execution roles and database access. To reproduce the release with an existing Docker Hub login:

```bash
./scripts/publish-images.sh
```

The publishing script targets Linux AMD64 and ARM64 by default. CloudNativePG and KEDA infrastructure use their official GHCR images. See the signal verification record for the actual release validation performed.

## Deploy to Kubernetes

Requirements: Kubernetes compatible with CloudNativePG 1.30.0, a default StorageClass, and enough resources for three database instances. The base configuration requires at least three schedulable nodes; its failure tolerance also depends on independent storage and an available control plane. Install Metrics Server for API HPA operation (on Minikube: `minikube addons enable metrics-server`).

```bash
./scripts/install-db-operator.sh
./scripts/install-signal-scaler.sh
kubectl apply -f kubernetes/namespace.yaml
python3 scripts/create-db-secrets.py kubernetes
kubectl apply -k kubernetes/
kubectl get clusters,databases,pods,services,pvc,hpa,scaledobjects -n homehub
```

For a one-node  demonstration, replace the apply command with:

```bash
kubectl apply -k kubernetes-local/
```

Allow the operator to initialize three database instances and provision the databases before expecting API readiness. APIs retry startup and Kubernetes restarts them if provisioning takes longer. The frontend is exposed on NodePort `30080`; on Minikube use `minikube service frontend -n homehub`. The operator installation includes cluster-scoped CRDs and permissions and runs two controller replicas.

Each database instance receives a separate 1 GiB PVC. `homehub-db-rw` follows the primary. Synchronous replication waits for one standby; if no standby is available, writes wait/fail instead of silently dropping the replication requirement. This is not a backup system.

Existing deployments need an explicit data migration before switching to the new databases. Applying this configuration does not import old data or automatically delete obsolete single-instance Deployments, Services, PVCs, or the old shared Secret. See [architecture and migration notes](docs/architecture/architecture.md).

## Verify

```bash
./scripts/verify.sh
./scripts/test-architecture.sh
python3 scripts/verify-db-ha.py --local-images
```

- Static checks: Python syntax, manifest rendering, frontend build.
- Architecture tests: disposable Docker PostgreSQL; concurrent initialization, rollback, readiness, connection limits, and database restart recovery. Requires Python 3 and Docker.
- HA tests: disposable Kubernetes namespace; separate service credentials, TLS verification, rejected cross-database logins, denied role escalation, primary Pod deletion, retained task data, subsequent writes, and unchanged API pods. Requires the installed CNPG operator. `--local-images` builds current APIs and requires a cluster that shares the local Docker image store, as OrbStack does. Omit the flag to test published release images instead.

The HA test deletes its test namespace on success; on failure it retains it and prints its name for diagnosis. It never touches the `homehub` namespace or the legacy Compose volume. Do not manually delete unrelated namespaces or volumes while cleaning up.

## Scope

This coursework version includes database-backed APIs, sample data, independent API scaling, database failover, and per-service database access control. Authentication/authorization for end users, full task editing/device controls, off-cluster backups, HTTP TLS ingress, and multi-tenant behavior are not implemented. A single-node demonstration cannot prove node/zone outage tolerance.

## Repository map

- `frontend/`: React and Nginx
- `services/`: independently containerized REST APIs and signal delivery roles
- `database/init/`: Compose-only database/role initialization
- `kubernetes/`: multi-node deployment with enforced database separation across nodes
- `kubernetes-local/`: one-node demonstration overlay
- `scripts/`: credential creation, operator installation, validation
- `tests/`: isolated database integration tests
- `docs/architecture/`: design, security, tradeoffs, migration
- `docs/verification/`: observed validation results
- `docs/report/`, `docs/video/`: coursework deliverable outlines

## Task walkthrough

Open the local page, select **Add task**, enter a name (with optional date and priority), and select **Create task**. The new task appears in the full list. Tick its checkbox to save completion, then refresh the browser: both the task and its completion state are loaded from PostgreSQL through the REST API. Unticking saves it as incomplete. Controls are disabled while saving; failed saves retain the draft or previous completion state and display an error. If a connection is interrupted, refresh to confirm the saved state before attempting to create a duplicate.

## Device walkthrough

Choose **Add device**, provide a name, room, initial reading, and sampling interval, then save. The first signal is queued immediately. Expand a **Signal delivery** row to inspect its JSON and refresh the page to verify persistence. Devices are simulated; a physical adapter can submit buffered readings with unique IDs to the REST endpoint. Unchanged samples are suppressed until the next heartbeat. See [signal architecture and upgrade commands](docs/architecture/device-signals.md) and [verification evidence](docs/verification/device-signals.md).
