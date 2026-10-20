import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
EXCHANGE = "vinylshelf.events"
QUEUE = "analytics.events"


def declare(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.queue_bind(queue=QUEUE, exchange=EXCHANGE, routing_key="#")
