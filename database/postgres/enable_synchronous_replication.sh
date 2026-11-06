#!/bin/sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER não definido}"
: "${POSTGRES_DB:?POSTGRES_DB não definido}"
: "${PGPASSWORD:?PGPASSWORD não definido}"

psql_postgres() {
  psql \
    --host=postgres \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --no-psqlrc \
    --tuples-only \
    --no-align \
    --set=ON_ERROR_STOP=1 \
    "$@"
}

tentativa=0
while [ "$tentativa" -lt 60 ]; do
  estado="$(psql_postgres --command \
    "SELECT state FROM pg_stat_replication WHERE application_name = 'studyspot_replica'")"
  if [ "$estado" = "streaming" ]; then
    break
  fi
  tentativa=$((tentativa + 1))
  sleep 1
done

if [ "$estado" != "streaming" ]; then
  printf 'A réplica não iniciou a transmissão em 60 segundos; replicação síncrona não ativada.\n' >&2
  exit 1
fi

psql_postgres <<'SQL'
ALTER SYSTEM SET synchronous_commit = 'on';
ALTER SYSTEM SET synchronous_standby_names = 'FIRST 1 (studyspot_replica)';
SELECT pg_reload_conf();
SQL

tentativa=0
while [ "$tentativa" -lt 30 ]; do
  estado="$(psql_postgres --command \
    "SELECT sync_state FROM pg_stat_replication WHERE application_name = 'studyspot_replica'")"
  if [ "$estado" = "sync" ]; then
    printf 'Replicação síncrona ativa.\n'
    exit 0
  fi
  tentativa=$((tentativa + 1))
  sleep 1
done

printf 'A réplica não confirmou o estado síncrono em 30 segundos.\n' >&2
exit 1
