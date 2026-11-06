#!/bin/sh
set -eu

PGDATA="${PGDATA:-/var/lib/postgresql/18/docker}"
export PGDATA
: "${POSTGRES_REPLICATION_PASSWORD:?POSTGRES_REPLICATION_PASSWORD não definido}"

ficheiro_pgpass=/var/lib/postgresql/.pgpass
umask 077
printf 'postgres:5432:replication:studyspot_replicator:%s\n' \
  "$POSTGRES_REPLICATION_PASSWORD" > "$ficheiro_pgpass"
chown postgres:postgres "$ficheiro_pgpass"
chmod 600 "$ficheiro_pgpass"

mkdir -p "$PGDATA"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  if [ -n "$(find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    printf 'PGDATA da réplica não está vazio e não contém uma cópia PostgreSQL válida.\n' >&2
    exit 1
  fi

  chown -R postgres:postgres /var/lib/postgresql
  gosu postgres pg_basebackup \
    --dbname="host=postgres port=5432 user=studyspot_replicator application_name=studyspot_replica passfile=$ficheiro_pgpass" \
    --pgdata="$PGDATA" \
    --format=plain \
    --wal-method=stream \
    --write-recovery-conf \
    --no-password \
    --progress
fi

exec /usr/local/bin/docker-entrypoint.sh postgres
