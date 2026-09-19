# HomeHub

HomeHub is a microservice-based household management application built for a Kubernetes coursework project. It presents household members, shared tasks, and simulated smart-home devices in one responsive web interface.

## Architecture

```text
Browser
  |
  v
Frontend (React + Nginx, NodePort 30080)
  |-------------------|------------------|
  v                   v                  v
Household API       Task API          Device API
  |                   |                  |
  +-------------------+------------------+
                      v
                 PostgreSQL
                      |
              PersistentVolumeClaim
```

The three FastAPI services have separate tables and REST endpoints. Kubernetes Deployments let each service scale independently. PostgreSQL stays at one replica and stores its data on a persistent volume.

## Run locally

Requirements: Docker with Compose support.

```bash
docker compose up --build
```

Open <http://localhost:8080>. Stop the stack without deleting its database:

```bash
docker compose down
```

Use `docker compose down -v` only when you intentionally want to remove the local database volume.

## REST APIs

| Service | Method | Endpoint | Purpose |
|---|---|---|---|
| Household | GET | `/api/households` | Household and member summary |
| Household | GET | `/api/households/members` | List members |
| Task | GET | `/api/tasks` | List tasks |
| Task | POST | `/api/tasks` | Create a task |
| Task | PATCH | `/api/tasks/{id}` | Update a task |
| Task | DELETE | `/api/tasks/{id}` | Delete a task |
| Device | GET | `/api/devices` | List simulated devices |
| Device | PATCH | `/api/devices/{id}` | Update device state |

Each API also exposes `/health` for Kubernetes probes.

## Docker images

Before Kubernetes deployment, replace `YOUR_DOCKERHUB_USERNAME` in `kubernetes/` and publish all four images:

```bash
docker build -t YOUR_DOCKERHUB_USERNAME/homehub-frontend:0.1.0 frontend
docker build -t YOUR_DOCKERHUB_USERNAME/homehub-household:0.1.0 services/household-service
docker build -t YOUR_DOCKERHUB_USERNAME/homehub-task:0.1.0 services/task-service
docker build -t YOUR_DOCKERHUB_USERNAME/homehub-device:0.1.0 services/device-service

docker push YOUR_DOCKERHUB_USERNAME/homehub-frontend:0.1.0
docker push YOUR_DOCKERHUB_USERNAME/homehub-household:0.1.0
docker push YOUR_DOCKERHUB_USERNAME/homehub-task:0.1.0
docker push YOUR_DOCKERHUB_USERNAME/homehub-device:0.1.0
```

## Deploy to Kubernetes

For Minikube, enable the metrics server so the autoscalers can receive CPU metrics:

```bash
minikube addons enable metrics-server
kubectl apply -k kubernetes/
kubectl get all,pvc,hpa -n homehub
minikube service frontend -n homehub
```

The frontend is also assigned NodePort `30080`. The database uses a 1 GiB PersistentVolumeClaim. The three APIs start with two replicas and have independent HorizontalPodAutoscalers.

## Current scope

This first version provides database-backed read APIs, task CRUD, device updates, sample data, health probes, responsive loading/error/empty states, local Compose orchestration, and Kubernetes deployment resources. Authentication, authorization, full create/edit forms, automated tests, and production secret management are planned follow-up work.

## Repository map

- `frontend/`: React interface and Nginx reverse proxy
- `services/`: independently containerized REST services
- `database/`: reserved for explicit migrations and seed assets
- `kubernetes/`: Kustomize-ready Kubernetes resources
- `docs/architecture/`: architecture diagrams and design decisions
- `docs/report/`: coursework report material
- `docs/video/`: demonstration plan
- `scripts/`: build and verification helpers

