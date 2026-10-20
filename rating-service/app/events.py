import json
import os
import time
from datetime import datetime, timezone

import pika

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
EXCHANGE = "vinylshelf.events"
QUEUE = "analytics.events"


def declare(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key="#")


def publish(routing_key: str, payload: dict) -> None:
    body = json.dumps({**payload, "event": routing_key, "ts": datetime.now(timezone.utc).isoformat()})
    for attempt in range(5):
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
            ch = conn.channel()
            declare(ch)
            ch.basic_publish(EXCHANGE, routing_key, body, pika.BasicProperties(delivery_mode=2, content_type="application/json"))
            conn.close()
            print(f"[rabbit] published {routing_key}: {body}", flush=True)
            return
        except pika.exceptions.AMQPError as e:
            print(f"[rabbit] publish retry {attempt + 1}: {e}", flush=True)
            time.sleep(1)
