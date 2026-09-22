# Architecture fix verification

Historical snapshot before the HA and credential-isolation change. The later [database HA verification](database-ha.md) supersedes the single-instance/shared-credential limitations below.

Verified at: 2026-09-20T16:16:47.282658+00:00

## Results

- `./scripts/test-architecture.sh`: passed all three integration test groups, covering each of the three APIs.
- Eight separate initializer processes per service produced exactly one seed set (3 household members, 4 tasks, 3 devices).
- Existing populated installations were adopted without duplicates.
- A forced failure after seed insertion rolled back both schema/seed changes and initialization markers; a subsequent successful initialization worked.
- Deleting all business rows and rerunning initialization did not recreate seed data.
- Pool exhaustion, a missing table, and an unreachable database produced HTTP 503 at `/ready`, while `/health` returned 200. Successful database access restored readiness.
- A third connection could not exceed the configured two-connection pool cap.
- Three real Uvicorn servers survived a stop/start of the isolated PostgreSQL container: `/ready` changed from 200 to 503 and back to 200; `/health` remained 200; API container start times did not change.
- `./scripts/verify.sh`: Python syntax, Kubernetes manifest rendering, and frontend production build passed.
- Compose configuration validation, shell syntax, and `git diff --check` passed.

## Scope and remaining limits

Tests used an anonymous disposable database volume, removed with the test containers and network. The existing `homehub_homehub-data` volume was not mounted or modified. An initial recovery test used tmpfs, which loses its contents on container stop; the test fixture was corrected to persistent temporary storage and the full suite rerun successfully.

This verifies the current source against PostgreSQL 17 and real containerized HTTP servers. It does not verify the changed Kubernetes probes in a live cluster. API manifests now target `0.1.1`; these new release images still need to be built/published before cluster deployment. The earlier node-pull report concerns `0.1.0` only.

Connection caps mitigate shared-database resource contention. One shared database instance and shared credentials remain; high availability, per-service database authorization, and load capacity are not established by these tests.
