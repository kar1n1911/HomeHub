#!/usr/bin/env sh
# Uses isolated containers and an ephemeral database; never mounts the app DB volume.
set -eu
cd "$(dirname "$0")/.."
run_id="homehub-architecture-$$"
network="$run_id"
database="$run_id-db"
runner="$run_id-test"
cleanup() {
  docker rm -fv "$runner" "$database" "$run_id-household" "$run_id-task" "$run_id-device" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker network create "$network" >/dev/null
docker run -d --name "$database" --network "$network" \
  -e POSTGRES_DB=homehub_test -e POSTGRES_USER=homehub -e POSTGRES_PASSWORD=test_only \
  postgres:17-alpine >/dev/null
attempt=0
until docker exec "$database" pg_isready -U homehub -d homehub_test >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker logs "$database"
    exit 1
  fi
  sleep 1
done
# Build the current dependencies and mount current source, rather than testing a published old app.
docker build -q -t homehub-architecture-test:local services/task-service >/dev/null
docker run --rm --name "$runner" --network "$network" \
  -e HOMEHUB_DISPOSABLE_DATABASE=1 \
  -e DATABASE_URL="postgresql+psycopg://homehub:test_only@$database:5432/homehub_test" \
  -v "$PWD:/workspace:ro" -w /workspace \
  homehub-architecture-test:local python tests/test_architecture.py

python3 tests/check_database_recovery.py "$network" "$database"
