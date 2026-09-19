# HomeHub architecture

## Component boundaries

### Frontend

The React frontend is the only browser-facing application. Nginx serves its static files and routes `/api/households`, `/api/tasks`, and `/api/devices` to the correct internal Kubernetes Service. The browser therefore uses one origin and does not need direct access to the API pods.

### Household Service

Owns household identity and member data. Its tables use the `household_` prefix so their ownership remains visible while the first version shares one PostgreSQL instance.

### Task Service

Owns chores and other shared work. It offers list, create, update, and delete operations without reading tables belonging to other services.

### Device Service

Owns simulated device state. Separating it from tasks allows device traffic to scale without allocating more Task Service pods.

### PostgreSQL

Runs as a separate deployment with one replica and a PersistentVolumeClaim. Each service owns its own tables. A later production design could move each service to a separate database without changing its public API.

## Architecture principles

- **API gateway at the edge:** Nginx provides one external entry point and path-based routing.
- **Service discovery:** internal Services provide stable DNS names for replaceable pods.
- **Stateless compute:** API containers keep durable state in PostgreSQL, so replicas can be added or replaced.
- **Independent scaling:** each application component has its own Deployment; each API has its own HPA.
- **Health-based recovery:** readiness and liveness probes prevent traffic from reaching unavailable containers.
- **Infrastructure as code:** application topology, configuration, probes, resources, storage, and scaling rules are versioned as YAML.

## Security baseline and next steps

The database is internal and is not exposed with NodePort. APIs are reached through the frontend proxy. Credentials are represented by a Kubernetes Secret rather than a ConfigMap, but the example development value remains in the repository for reproducibility and must be replaced in a real environment. Production improvements should include an external secret manager, TLS ingress, authenticated users, role-based authorization, input rate limiting, restrictive NetworkPolicies, non-root containers, image scanning, and regular database backups.

