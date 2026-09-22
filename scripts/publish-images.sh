#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
# Uses the user's existing Docker Hub login. No credential is written to source.
# Override PLATFORMS for an architecture-specific classroom build.
docker buildx inspect homehub-release >/dev/null 2>&1 || docker buildx create --name homehub-release --driver docker-container
for service in frontend household task device alertmanager; do
  context="services/$service-service"
  if [ "$service" = frontend ]; then context=frontend; fi
  docker buildx build --builder homehub-release --platform "${PLATFORMS:-linux/amd64,linux/arm64}" \
    --tag "kar1n1911/homehub-$service:${VERSION:-0.2.0}" --push "$context"
done
