#!/bin/sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER não definido}"
: "${POSTGRES_DB:?POSTGRES_DB não definido}"
: "${PGPASSWORD:?PGPASSWORD não definido}"
: "${POSTGRES_REPLICATION_PASSWORD:?POSTGRES_REPLICATION_PASSWORD não definido}"

psql \
  --host=postgres \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" \
  --no-psqlrc \
  --set=ON_ERROR_STOP=1 <<'SQL'
\getenv replication_password POSTGRES_REPLICATION_PASSWORD

SELECT format(
    'CREATE ROLE studyspot_replicator WITH LOGIN REPLICATION PASSWORD %L',
    :'replication_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'studyspot_replicator'
)
\gexec

SELECT format(
    'ALTER ROLE studyspot_replicator WITH LOGIN REPLICATION PASSWORD %L',
    :'replication_password'
)
WHERE EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'studyspot_replicator'
)
\gexec
SQL
