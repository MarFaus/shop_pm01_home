#!/bin/sh
# Запуск реплики PostgreSQL.
# При первом запуске (том пустой) копирует всю базу с primary через pg_basebackup,
# дальше реплика получает изменения потоком WAL и доступна только на чтение.
set -e

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Реплика пустая — копирую базу с $PRIMARY_HOST..."
  until pg_isready -h "$PRIMARY_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
    sleep 2
  done
  mkdir -p "$PGDATA"
  chown postgres:postgres "$PGDATA"
  chmod 700 "$PGDATA"
  # Слот репликации: primary хранит WAL, пока реплика его не получит, даже если
  # она долго лежала. Слот от прошлой жизни (том реплики пересоздали) удаляем.
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$PRIMARY_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT pg_drop_replication_slot(slot_name) FROM pg_replication_slots WHERE slot_name = '$SLOT_NAME'"
  # -X stream  — вместе с файлами передать WAL, накопившийся за время копирования
  # -R         — записать primary_conninfo, имя слота и standby.signal: «ты реплика»
  # -C -S      — создать слот и сразу им пользоваться
  # --checkpoint=fast — не ждать планового checkpoint на primary
  su-exec postgres env PGPASSWORD="$REPLICATION_PASSWORD" \
    pg_basebackup -h "$PRIMARY_HOST" -U replicator -D "$PGDATA" \
                  -X stream -R -C -S "$SLOT_NAME" --checkpoint=fast
  echo "Копирование завершено"
fi

# Запускаем сервер от пользователя postgres с аргументами из command:
exec su-exec postgres postgres "$@"
