"""Кэш в Redis по схеме cache-aside.

Приложение само решает, что кэшировать:
  1. ищем значение в кэше;
  2. нет (MISS) — берём из БД и кладём в кэш с TTL;
  3. данные изменились — удаляем ключ (инвалидация).

Кэш — ускоритель, а не хранилище: если Redis недоступен, приложение
продолжает работать напрямую с БД (все ошибки Redis глушим).
"""
import asyncio
import datetime
import decimal
import json
import logging
import os

import redis.asyncio as redis
from prometheus_client import Counter
from redis.asyncio.cluster import ClusterNode, RedisCluster

log = logging.getLogger("cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Если задан список узлов — работаем с Redis Cluster (лаб 4), иначе с одним Redis
REDIS_CLUSTER_NODES = os.getenv("REDIS_CLUSTER_NODES", "")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))  # время жизни по умолчанию, секунд
# Потолок на любую операцию с кэшем. Во время failover клиент кластера
# переподключается и ретраит секундами — пользователь ждать не должен.
CACHE_OP_TIMEOUT = float(os.getenv("CACHE_OP_TIMEOUT", "0.3"))

# hit — нашли в кэше, miss — нет, error — Redis не ответил
CACHE_REQUESTS = Counter("cache_requests_total", "Обращения к кэшу", ["result"])

_client: redis.Redis | RedisCluster | None = None


def _default(value):
    # asyncpg возвращает Decimal и datetime — JSON их не знает
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    raise TypeError(f"не сериализуется: {type(value)}")


async def init() -> None:
    global _client
    # Короткие таймауты: лучше сходить в БД, чем ждать зависший кэш
    opts = dict(decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5)
    if REDIS_CLUSTER_NODES:
        # Клиент кластера сам считает слот ключа (CRC16(key) % 16384)
        # и идёт на нужный мастер; после failover обновляет карту узлов.
        nodes = [ClusterNode(*addr.split(":")) for addr in REDIS_CLUSTER_NODES.split(",")]
        _client = RedisCluster(startup_nodes=nodes, **opts)
    else:
        _client = redis.from_url(REDIS_URL, **opts)


async def close() -> None:
    if _client is not None:
        await _client.aclose()


async def get(key: str):
    """Значение из кэша или None (нет ключа или Redis недоступен)."""
    try:
        raw = await asyncio.wait_for(_client.get(key), CACHE_OP_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis get %s: %r", key, exc)
        CACHE_REQUESTS.labels("error").inc()
        return None
    if raw is None:
        CACHE_REQUESTS.labels("miss").inc()
        return None
    CACHE_REQUESTS.labels("hit").inc()
    return json.loads(raw)


async def set(key: str, value, ttl: int | None = None) -> None:
    try:
        data = json.dumps(value, default=_default, ensure_ascii=False)
        await asyncio.wait_for(_client.set(key, data, ex=ttl or CACHE_TTL), CACHE_OP_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis set %s: %r", key, exc)


async def delete(key: str) -> None:
    try:
        await asyncio.wait_for(_client.delete(key), CACHE_OP_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis delete %s: %r", key, exc)


async def ping() -> bool:
    try:
        return bool(await asyncio.wait_for(_client.ping(), CACHE_OP_TIMEOUT))
    except Exception:  # noqa: BLE001
        return False
