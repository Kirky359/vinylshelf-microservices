"""RabbitMQ consumer with Transactional Inbox; confirms SAGA steps in collection-service."""
import asyncio
import json
import logging
import threading
import time

import pika
from prometheus_client import Counter

from src.analytics import service
from src.config import settings
from src.discovery import call
from src.inbox import service as inbox_service
from src.messaging import constants as mq_constants
from src.messaging.broker import declare
from src.observability import bind_trace, log_event

EVENTS = Counter("analytics_events_total", "Events received from RabbitMQ", ["event", "result"])
log = logging.getLogger("analytics")
_stop = threading.Event()
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def stop() -> None:
    _stop.set()


def confirm_saga(saga_id: str) -> bool:
    """Tell the producer's saga coordinator that the event is processed (sync call through Consul)."""
    for attempt in range(3):
        try:
            fut = asyncio.run_coroutine_threadsafe(
                call("collection-service", "POST", "/saga/confirm", json={"saga_id": saga_id}), _loop)
            r = fut.result(timeout=10)
            log_event(log, "saga confirm", saga_id=saga_id, status=r.status_code)
            return r.status_code == 200
        except Exception as e:
            print(f"[analytics] confirm retry {attempt + 1}/3: {e!r}", flush=True)
            time.sleep(1)
    return False


def callback(ch, method, properties, body):
    event = json.loads(body)
    with bind_trace(event.get("trace_id")):
        _handle(ch, method, event)


def _handle(ch, method, event):
    mid = event.get("message_id")
    # only the event that started a saga needs a confirmation (not e.g. album_completion_cancelled)
    saga_id = event.get("saga_id") if event["event"] == "collection.album_completed" else None
    log_event(log, f"received {event['event']}", event=event["event"], message_id=mid, saga_id=saga_id)
    if mid and inbox_service.get(mid):  # Transactional Inbox: this message_id was already handled
        inbox_service.mark_duplicate(mid)
        EVENTS.labels(event["event"], "duplicate").inc()
        log_event(log, "duplicate message detected", logging.WARNING, message_id=mid)
        if saga_id:
            confirm_saga(saga_id)  # confirmation is idempotent, the first one may have been lost
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    try:
        service.handle(event)
    except Exception as e:
        EVENTS.labels(event["event"], "failed").inc()
        log_event(log, f"failed to process message: {e}", logging.ERROR, message_id=mid)
        if mid:
            inbox_service.save(event, "failed")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # -> dead letter exchange -> DLQ
        return
    if mid:
        inbox_service.save(event, "processed")
    EVENTS.labels(event["event"], "processed").inc()
    log_event(log, "event processed and saved to inbox", message_id=mid)
    if saga_id and not confirm_saga(saga_id):
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)  # redelivery; inbox turns it into a duplicate
        time.sleep(1)
        return
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_forever() -> None:
    while not _stop.is_set():
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(settings.rabbit_host))
            ch = conn.channel()
            declare(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(mq_constants.QUEUE, callback)
            print("[analytics] waiting for events...", flush=True)
            while not _stop.is_set():
                conn.process_data_events(time_limit=1)
            conn.close()
        except pika.exceptions.AMQPError as exc:
            print(f"[analytics] broker not ready: {exc}", flush=True)
            time.sleep(2)
        except Exception as exc:  # a bad message must not kill the consumer thread
            print(f"[analytics] consumer error: {exc!r}", flush=True)
            time.sleep(2)


def start() -> None:
    threading.Thread(target=consume_forever, daemon=True).start()
