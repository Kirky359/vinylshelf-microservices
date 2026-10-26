EXCHANGE = "vinylshelf.events"
QUEUE = "analytics.events"
DLX = "vinylshelf.dlx"
DLQ = "analytics.events.dlq"
MESSAGE_TTL_MS = 30000  # a message that is not consumed in 30 s expires into the DLQ
