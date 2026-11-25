#!/bin/sh
# Подготовка primary к потоковой репликации.
# Выполняется ОДИН раз — при первом запуске пустой базы (после 01_schema.sql).
set -e

# Отдельный пользователь только для репликации
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPLICATION_PASSWORD:-replicator}';
SQL

# Разрешаем репликам подключаться для репликации (с паролем).
# Обычное правило "host all all all" на репликацию не распространяется.
echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"
