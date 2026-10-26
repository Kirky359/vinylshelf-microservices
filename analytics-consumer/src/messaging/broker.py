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
