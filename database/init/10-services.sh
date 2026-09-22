#!/usr/bin/env sh
set -eu
# This runs only for the NEW Compose volume; the legacy homehub-data is not mounted.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
SQL
for service in household task device alertmanager receiver; do
  SERVICE_PASSWORD=$(cat "/run/secrets/${service}_password")
  export SERVICE_PASSWORD
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    --set=service_role="homehub_$service" <<'SQL'
\getenv service_password SERVICE_PASSWORD
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', :'service_role', :'service_password') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'service_role') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'service_role', :'service_role') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'service_role') \gexec
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'service_role') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'service_role', :'service_role') \gexec
SQL
  unset SERVICE_PASSWORD
done
