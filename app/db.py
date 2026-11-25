"""Подключение к PostgreSQL с разделением чтения и записи.

Запись (и чтение, где важна свежесть) — на primary.
Чтение каталога — на реплики по очереди (round-robin).
Реплика недоступна — запрос уходит на primary, реплика пропускается 10 секунд.
"""
import itertools
import logging
import os
import time

import asyncpg

log = logging.getLogger("db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@localhost:5432/shop")
# Адреса реплик через запятую. Пусто — всё читаем с primary.
DATABASE_REPLICA_URLS = [u for u in os.getenv("DATABASE_REPLICA_URLS", "").split(",") if u]
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
REPLICA_RETRY_SEC = 10
# Чтение с реплики дольше этого — считаем реплику недоступной и идём на primary.
# Наши запросы с индексами укладываются в десятки миллисекунд.
REPLICA_TIMEOUT_SEC = float(os.getenv("REPLICA_TIMEOUT_SEC", "1.0"))

# Ошибки «не достучались до сервера» — повод переключиться на primary.
# (TimeoutError в Python — подкласс OSError, таймаут тоже сюда попадает.)
# Ошибки в самом SQL (синтаксис и т.п.) не ловим: на primary они повторятся.
CONNECTION_ERRORS = (OSError, asyncpg.PostgresConnectionError,
                     asyncpg.InterfaceError, asyncpg.CannotConnectNowError)


def is_connection_error(exc: Exception) -> bool:
    if isinstance(exc, CONNECTION_ERRORS):
        return True
    # Через PgBouncer недоступный сервер приходит не обрывом сокета, а ошибкой
    # протокола: SQLSTATE класса 08 (connection exception) с текстом от pgbouncer
    sqlstate = getattr(exc, "sqlstate", None) or ""
    return sqlstate.startswith("08") or "pgbouncer" in str(exc).lower()


async def _no_reset(conn: asyncpg.Connection) -> None:
    """Не сбрасывать сессию при возврате соединения в пул.

    По умолчанию asyncpg после КАЖДОГО запроса шлёт RESET ALL,
    pg_advisory_unlock_all() и CLOSE ALL — лишний сетевой круг.
    Мы не храним состояние в сессии (SET, блокировки, курсоры),
    а PgBouncer в режиме transaction и так отдаёт соединение другим.
    Это видно в pg_stat_statements (db/sql/top_queries.sql).
    """


class Database:
    def __init__(self) -> None:
        self.primary: asyncpg.Pool | None = None
        self.replicas: list[asyncpg.Pool] = []
        self._down_until: dict[int, float] = {}   # номер реплики → когда пробовать снова
        self._rr = itertools.cycle([0])

    async def connect(self) -> None:
        self.primary = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=DB_POOL_MAX,
                                                 reset=_no_reset)
        # min_size=0: соединения с репликой открываются при первом запросе,
        # поэтому приложение стартует, даже если реплика ещё не поднялась
        self.replicas = [
            await asyncpg.create_pool(url, min_size=0, max_size=DB_POOL_MAX, timeout=1,
                                      reset=_no_reset)
            for url in DATABASE_REPLICA_URLS
        ]
        if self.replicas:
            self._rr = itertools.cycle(range(len(self.replicas)))

    async def close(self) -> None:
        for pool in [self.primary, *self.replicas]:
            if pool is not None:
                await pool.close()

    def _next_replica(self) -> int | None:
        """Следующая живая реплика по кругу или None."""
        now = time.monotonic()
        for _ in range(len(self.replicas)):
            i = next(self._rr)
            if self._down_until.get(i, 0) <= now:
                return i
        return None

    async def _read(self, method: str, query: str, *args):
        i = self._next_replica()
        if i is not None:
            try:
                return await getattr(self.replicas[i], method)(query, *args,
                                                               timeout=REPLICA_TIMEOUT_SEC)
            except Exception as exc:  # noqa: BLE001
                if not is_connection_error(exc):
                    raise
                log.warning("реплика %d недоступна (%r) — читаю с primary", i, exc)
                self._down_until[i] = time.monotonic() + REPLICA_RETRY_SEC
        return await getattr(self.primary, method)(query, *args)

    # Чтение с реплики (данные могут отставать на доли секунды)
    async def fetch_ro(self, query: str, *args):
        return await self._read("fetch", query, *args)

    async def fetchrow_ro(self, query: str, *args):
        return await self._read("fetchrow", query, *args)

    async def replica_status(self) -> list[bool]:
        status = []
        for pool in self.replicas:
            try:
                status.append(await pool.fetchval("SELECT pg_is_in_recovery()",
                                                  timeout=REPLICA_TIMEOUT_SEC))
            except Exception:  # noqa: BLE001
                status.append(False)
        return status


db = Database()
