# Kubernetes node image pull verification

Checked at: 2026-09-20T16:09:51.410895+00:00
Context and node: `orbstack`

Four temporary Pods used `imagePullPolicy: Always` and ran `/bin/sh -c` with an echo command. All completed successfully. This verifies registry resolution and container execution on this node; cached layers may be reused. It does not verify application startup, database connectivity, or a fresh uncached download.

- device: Succeeded; exit code 0
  - `docker-pullable://kar1n1911/homehub-device@sha256:059c45a5d39649e9d0dcea9758b8952bd17d10bae8dedeead32c524d9c01606f`
- frontend: Succeeded; exit code 0
  - `docker-pullable://kar1n1911/homehub-frontend@sha256:06a8313ffac073eec8d4769e3bc91b4cf526b62a9245cdc1dab4bdef6d50cf32`
- household: Succeeded; exit code 0
  - `docker-pullable://kar1n1911/homehub-household@sha256:b48460b358d6d72b58ecdc36ae0bbf1eeb3cb9f503ed4bbafa72bf41c004f2bf`
- task: Succeeded; exit code 0
  - `docker-pullable://kar1n1911/homehub-task@sha256:e1952f4f6d6c4d5162205216348a8fda32435e2ad6411e79d17ae3a95ff8fd22`

## Kubernetes events

```text
LAST SEEN   TYPE     REASON      OBJECT          MESSAGE
23s         Normal   Scheduled   pod/household   Successfully assigned homehub-pull-check/household to orbstack
23s         Normal   Scheduled   pod/frontend    Successfully assigned homehub-pull-check/frontend to orbstack
23s         Normal   Scheduled   pod/task        Successfully assigned homehub-pull-check/task to orbstack
23s         Normal   Scheduled   pod/device      Successfully assigned homehub-pull-check/device to orbstack
23s         Normal   Pulling     pod/device      Pulling image "docker.io/kar1n1911/homehub-device:0.1.0"
23s         Normal   Pulling     pod/household   Pulling image "docker.io/kar1n1911/homehub-household:0.1.0"
23s         Normal   Pulling     pod/frontend    Pulling image "docker.io/kar1n1911/homehub-frontend:0.1.0"
23s         Normal   Pulling     pod/task        Pulling image "docker.io/kar1n1911/homehub-task:0.1.0"
22s         Normal   Started     pod/frontend    Container started
22s         Normal   Created     pod/frontend    Container created
22s         Normal   Pulled      pod/household   Successfully pulled image "docker.io/kar1n1911/homehub-household:0.1.0" in 1.169s (1.169s including waiting). Image size: 217569260 bytes.
22s         Normal   Started     pod/device      Container started
22s         Normal   Created     pod/device      Container created
22s         Normal   Created     pod/household   Container created
22s         Normal   Started     pod/household   Container started
22s         Normal   Pulled      pod/device      Successfully pulled image "docker.io/kar1n1911/homehub-device:0.1.0" in 1.23s (1.23s including waiting). Image size: 217570521 bytes.
22s         Normal   Pulled      pod/frontend    Successfully pulled image "docker.io/kar1n1911/homehub-frontend:0.1.0" in 1.149s (1.149s including waiting). Image size: 49885918 bytes.
22s         Normal   Pulled      pod/task        Successfully pulled image "docker.io/kar1n1911/homehub-task:0.1.0" in 1.236s (1.236s including waiting). Image size: 217574513 bytes.
22s         Normal   Created     pod/task        Container created
22s         Normal   Started     pod/task        Container started
```
