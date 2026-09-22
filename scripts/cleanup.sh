#!/usr/bin/env bash
# Remove only this project's application workloads. Never prune host resources.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target=all
dry_run=false
context=orbstack
docker_context=orbstack
usage() {
  cat <<'HELP'
Usage: ./scripts/cleanup.sh [all|compose|k8s] [--dry-run] [--context NAME] [--docker-context NAME]

Default: all (HomeHub Compose + Kubernetes application workloads).
  compose   Remove HomeHub Compose containers and network; keep volumes/images.
  k8s       Remove HomeHub application Deployments and autoscalers in namespace
            homehub. Keep PostgreSQL running, PVCs, Secrets, Services and operators.
  all       Run both modes.
  --dry-run Print the exact commands without changing anything.
  --context Explicit Kubernetes context (default: orbstack, never current-context).
  --docker-context Explicit Docker context (default: orbstack).

This stops application access. No database data or credentials are deleted.
Restart Compose: docker compose up -d
Restart local Kubernetes: ./scripts/deploy-k8s.sh
HELP
}
chosen=false
while (($#)); do
  case "$1" in
    all|compose|k8s)
      if "$chosen"; then echo 'Specify only one cleanup target.' >&2; exit 2; fi
      target="$1"; chosen=true; shift ;;
    --dry-run) dry_run=true; shift ;;
    --docker-context)
      if (($# < 2)) || [[ -z "$2" || "$2" == -* ]]; then echo '--docker-context needs a name.' >&2; exit 2; fi
      docker_context="$2"; shift 2 ;;
    --context)
      if (($# < 2)) || [[ -z "$2" || "$2" == -* ]]; then echo '--context needs a name.' >&2; exit 2; fi
      context="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
run() {
  printf '+'; printf ' %q' "$@"; printf '\n'
  if ! "$dry_run"; then "$@"; fi
}
# Check every requested runtime before starting either cleanup.
if ! "$dry_run"; then
  if [[ "$target" != k8s ]]; then
    command -v docker >/dev/null
    docker --context "$docker_context" compose version >/dev/null
    docker --context "$docker_context" info >/dev/null
  fi
  if [[ "$target" != compose ]]; then
    command -v kubectl >/dev/null
    kubectl --context "$context" get namespace homehub --ignore-not-found >/dev/null
  fi
fi
if [[ "$target" != compose ]]; then
  echo "Kubernetes: context=$context namespace=homehub (database retained)"
  # Delete the owner of the KEDA-generated HPA first, then the ordinary HPAs.
  run kubectl --context "$context" -n homehub delete -f "$ROOT/kubernetes/config/signal-scaling.yaml" --ignore-not-found --timeout=60s
  run kubectl --context "$context" -n homehub delete -f "$ROOT/kubernetes/config/hpa.yaml" --ignore-not-found --timeout=60s
  run kubectl --context "$context" -n homehub delete deployment frontend household-service task-service device-service alertmanager signal-worker signal-receiver --ignore-not-found --cascade=foreground --timeout=120s
fi
if [[ "$target" != k8s ]]; then
  # A fixed project name prevents COMPOSE_PROJECT_NAME or caller cwd changing scope.
  run docker --context "$docker_context" compose --project-name homehub --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" down --timeout 30
fi
if "$dry_run"; then
  echo 'Preview complete. No resources changed.'
else
  echo 'HomeHub cleanup complete. Database data, credentials and images retained.'
fi
