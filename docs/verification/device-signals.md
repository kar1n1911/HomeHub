# Device registration and signal delivery verification

Initial checks: 2026-09-21. Published-release checks: 2026-09-22. Environment: local Docker Compose and OrbStack Kubernetes (ARM64), using the actual frontend proxy and PostgreSQL storage.

## Observed results

- Browser: added **Balcony temperature**, room **Balcony**, reading **19.8 C**, interval **30 seconds**. Reloaded the page and verified the saved device and delivered signal. Existing completed task **Prepare groceries for Friday** remained intact.
- Compose integration: source UUID replay accepted without duplicate data; conflicting UUID content rejected with 409; stopped receiver retained pending messages; service restarts retained the queue; two workers delivered concurrently; forced redelivery after receiver commit produced one receiver record; an expired worker lease was reclaimed; unchanged due samples were suppressed; an eligible heartbeat was emitted. See [machine-readable results](signal-delivery.json).
- Kubernetes: KEDA 2.20.2 scaled workers **0 → 4 → 0**. The test stopped the receiver, submitted **45 distinct readings**, replaced worker Pods, restored the receiver, and verified all test IDs directly in the receiver database. See [machine-readable results](signal-scaling.json).
- Regression: concurrent initialization, seed rollback, readiness and pool checks passed. All three original HTTP services returned health 200 / readiness 503 while the disposable database was down, and recovered without API restarts.
- Fixed an issue exposed by the restart test: the frontend proxy now refreshes backend DNS addresses instead of retaining stale container addresses. This is verified through the actual external proxy.
- Security: Alertmanager and receiver connections used TLS and rejected access to another service database; unauthenticated internal signal requests returned 401. See [database isolation checks](signal-db-isolation.json).
- Static Python, frontend build, and both Kustomize render checks passed. Desktop/mobile browser layouts were inspected; dark-panel contrast and padding were corrected.

The tests intentionally leave their named verification devices and readings. The Compose and Kubernetes installations use separate databases; their device lists differ. Kubernetes uses three database instances with separate PVCs on one physical host, which cannot demonstrate host-loss tolerance.

## Access and repeatability

- Compose: `http://localhost:8080`
- Kubernetes NodePort: `http://localhost:30080`
- Compose fault test: `python3 tests/verify_signal_delivery.py`
- Kubernetes scaling test: `python3 scripts/verify-signal-scaling.py`
- These fault tests temporarily stop the receiver and replace test/demo processing instances; use only the local demonstration environment.

Delivery is at least once with receiver deduplication. JSON is not encrypted. Real device adapters, user authentication, ingress TLS, off-cluster backups, and audit retention still require additional work. The observed tests do not prove data survival under every possible failure.

## Published release 0.2.0

All five application images were published to Docker Hub under `kar1n1911`, with Linux AMD64 and ARM64 manifests. The OrbStack node pulled and ran the release with `imagePullPolicy: Always`; cached layers may be reused. Six always-running deployments became ready. Backend source hashes inside the running containers matched the workspace. See [registry manifests](release-images.json) and [running node image IDs](release-node-pull.json). Repeat the read-only checks with `python3 scripts/verify-release-images.py` when the demo is healthy.

The full Kubernetes fault/scaling test was repeated against the published Alertmanager image on 2026-09-22 and again passed **0 → 4 → 0**, with all **45** submitted IDs received. Its report records the worker image ID.

Through `http://localhost:30080`, the browser-created task **Verify Kubernetes household workflow** remained completed after reload and the release rollout. The published frontend also added **Kitchen temperature**, reading **22.1 C**, interval **30 seconds**; reload retained it and displayed its JSON signal as **Delivered**.
