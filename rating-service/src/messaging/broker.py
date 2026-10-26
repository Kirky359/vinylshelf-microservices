import json
import time
from datetime import datetime, timezone

import pika

from src.config import settings
from src.messaging import constants


def declare(channel):
    channel.exchange_declare(exchange=constants.EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=constants.DLX, exchange_type="direct", durable=True)
    channel.queue_declare(queue=constants.DLQ, durable=True)
    channel.queue_bind(queue=constants.DLQ, exchange=constants.DLX, routing_key=constants.QUEUE)
    channel.queue_declare(queue=constants.QUEUE, durable=True, arguments={
        "x-dead-letter-exchange": constants.DLX,
        "x-dead-letter-routing-key": constants.QUEUE,
        "x-message-ttl": constants.MESSAGE_TTL_MS,
    })
    channel.queue_bind(queue=constants.QUEUE, exchange=constants.EXCHANGE, routing_key="#")


def publish(routing_key: str, payload: dict) -> None:
    body = json.dumps({**payload, "event": routing_key, "ts": datetime.now(timezone.utc).isoformat()})
    for attempt in range(5):
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(settings.rabbit_host))
            ch = conn.channel()
            declare(ch)
            ch.basic_publish(constants.EXCHANGE, routing_key, body,
                             pika.BasicProperties(delivery_mode=2, content_type="application/json"))
            conn.close()
            print(f"[rabbit] published {routing_key}: {body}", flush=True)
            return
        except pika.exceptions.AMQPError as e:
            print(f"[rabbit] publish retry {attempt + 1}: {e}", flush=True)
            time.sleep(1)
