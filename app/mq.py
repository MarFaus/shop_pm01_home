"""Очередь RabbitMQ: публикация заказов на обработку.

API не ждёт платёжный шлюз: оно резервирует товар, кладёт номер заказа
в очередь и сразу отвечает. Оплату выполняет consumer.py в своём темпе.
"""
import json
import logging
import os

import aio_pika

log = logging.getLogger("mq")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://shop:shop@localhost:5672/")
QUEUE = "orders"
DEAD_QUEUE = "orders.dead"   # сюда попадают сообщения, которые не удалось обработать

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def declare(channel: aio_pika.abc.AbstractChannel) -> aio_pika.abc.AbstractQueue:
    """Объявить очереди. Вызывают и API, и consumer — кто стартует первым."""
    await channel.declare_queue(DEAD_QUEUE, durable=True)
    # durable — очередь переживает перезапуск RabbitMQ;
    # x-dead-letter-* — отклонённые сообщения уходят в orders.dead, а не теряются
    return await channel.declare_queue(
        QUEUE, durable=True,
        arguments={"x-dead-letter-exchange": "", "x-dead-letter-routing-key": DEAD_QUEUE},
    )


async def init() -> None:
    global _connection, _channel
    # connect_robust сам переподключается, если RabbitMQ перезапустился
    _connection = await aio_pika.connect_robust(RABBITMQ_URL)
    # publisher_confirms: publish() ждёт подтверждения, что брокер принял сообщение
    _channel = await _connection.channel(publisher_confirms=True)
    await declare(_channel)


async def close() -> None:
    if _connection is not None:
        await _connection.close()


async def publish_order(order_id: int) -> None:
    message = aio_pika.Message(
        json.dumps({"order_id": order_id}).encode(),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,   # сообщение пишется на диск
    )
    await _channel.default_exchange.publish(message, routing_key=QUEUE)
