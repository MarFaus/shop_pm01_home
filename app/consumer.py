"""Обработчик очереди заказов: «оплачивает» заказ и переводит его в processed.

Запуск: python consumer.py (в Docker — отдельный сервис consumer).
"""
import asyncio
import json
import logging
import os

import aio_pika
import asyncpg

import mq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("consumer")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@localhost:5432/shop")
PAYMENT_DELAY = float(os.getenv("PAYMENT_DELAY_SEC", "0.2"))
# Сколько сообщений consumer берёт одновременно. Пока одно ждёт «шлюз»,
# обрабатываются другие: 50 × (1 / 0,2 с) ≈ 250 заказов в секунду.
PREFETCH = int(os.getenv("CONSUMER_PREFETCH", "50"))
# Заказы, «застрявшие» в pending дольше этого (сообщение потерялось), отправляем снова
STUCK_AFTER = os.getenv("STUCK_AFTER", "5 minutes")


async def process(pool: asyncpg.Pool, message: aio_pika.abc.AbstractIncomingMessage) -> None:
    # requeue=False: при исключении сообщение уходит в orders.dead, а не по кругу
    async with message.process(requeue=False):
        order_id = json.loads(message.body)["order_id"]
        await asyncio.sleep(PAYMENT_DELAY)   # имитация платёжного шлюза
        # AND status = 'pending' — идемпотентность: повторное сообщение ничего не испортит
        result = await pool.execute(
            """UPDATE orders SET status = 'processed', processed_at = now()
               WHERE id = $1 AND status = 'pending'""",
            order_id,
        )
        if result != "UPDATE 1":
            log.info("заказ %s уже обработан или не найден", order_id)


async def resend_stuck(pool: asyncpg.Pool) -> None:
    """Страховка: API создало заказ, но не смогло положить его в очередь."""
    while True:
        await asyncio.sleep(60)
        try:
            ids = await pool.fetch(
                f"""SELECT id FROM orders
                    WHERE status = 'pending' AND created_at < now() - interval '{STUCK_AFTER}'
                    LIMIT 500"""
            )
            for row in ids:
                await mq.publish_order(row["id"])
            if ids:
                log.warning("повторно отправлено застрявших заказов: %d", len(ids))
        except Exception as exc:  # noqa: BLE001
            log.warning("resend_stuck: %r", exc)


async def main() -> None:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    await mq.init()   # соединение для повторной отправки

    connection = await aio_pika.connect_robust(mq.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=PREFETCH)
    queue = await mq.declare(channel)

    async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            await process(pool, message)
        except Exception as exc:  # noqa: BLE001
            log.error("не удалось обработать сообщение: %r", exc)

    await queue.consume(on_message)
    log.info("consumer запущен, prefetch=%d, задержка шлюза=%.1f с", PREFETCH, PAYMENT_DELAY)
    await resend_stuck(pool)   # работает бесконечно


if __name__ == "__main__":
    asyncio.run(main())
