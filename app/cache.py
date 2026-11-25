"""Кэш в Redis по схеме cache-aside.

Приложение само решает, что кэшировать:
  1. ищем значение в кэше;
  2. нет (MISS) — берём из БД и кладём в кэш с TTL;
  3. данные изменились — удаляем ключ (инвалидация).

Кэш — ускоритель, а не хранилище: если Redis недоступен, приложение
продолжает работать напрямую с БД (все ошибки Redis глушим).
"""
import datetime
import decimal
import json
import logging
import os

import redis.asyncio as redis

log = logging.getLogger("cache")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))  # время жизни по умолчанию, секунд

_client: redis.Redis | None = None


def _default(value):
    # asyncpg возвращает Decimal и datetime — JSON их не знает
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    raise TypeError(f"не сериализуется: {type(value)}")


async def init() -> None:
    global _client
    _client = redis.from_url(REDIS_URL, decode_responses=True,
                             socket_timeout=0.5, socket_connect_timeout=0.5)


async def close() -> None:
    if _client is not None:
        await _client.aclose()


async def get(key: str):
    """Значение из кэша или None (нет ключа или Redis недоступен)."""
    try:
        raw = await _client.get(key)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis get %s: %s", key, exc)
        return None
    return None if raw is None else json.loads(raw)


async def set(key: str, value, ttl: int | None = None) -> None:
    try:
        await _client.set(key, json.dumps(value, default=_default, ensure_ascii=False),
                          ex=ttl or CACHE_TTL)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis set %s: %s", key, exc)


async def delete(key: str) -> None:
    try:
        await _client.delete(key)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis delete %s: %s", key, exc)


async def ping() -> bool:
    try:
        return bool(await _client.ping())
    except Exception:  # noqa: BLE001
        return False
