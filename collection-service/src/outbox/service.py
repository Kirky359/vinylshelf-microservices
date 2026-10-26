"""Outbox: events are written in the caller's transaction and relayed to RabbitMQ by a dispatcher (at-least-once)."""
import json
import threading
import time
import uuid

import pika

from src import database as db
from src.config import settings
from src.messaging import constants as mq_constants
from src.messaging.broker import declare
from src.outbox import constants
from src.utils import now

_stop = threading.Event()


def stop() -> None:
    _stop.set()


def add_event(conn, event_type: str, payload: dict, saga_id: str | None = None) -> str:
    """Write an event into the outbox using the caller's transaction (same commit as the data change)."""
    msg_id = str(uuid.uuid4())
    body = {"message_id": msg_id, "saga_id": saga_id, **payload, "event": event_type, "ts": now()}
    conn.execute(
        "INSERT INTO outbox (id, saga_id, event_type, payload, created_at) VALUES (?,?,?,?,?)",
        (msg_id, saga_id, event_type, json.dumps(body), now()),
    )
    return msg_id


def _fail_or_retry(conn, row, error: str) -> None:
    attempts = row["attempts"] + 1
    if attempts >= constants.MAX_ATTEMPTS:
        conn.execute("UPDATE outbox SET status='failed', attempts=?, last_error=? WHERE id=?",
                     (attempts, error, row["id"]))
        print(f"[outbox] event {row['id']} marked as failed after {attempts} attempts: {error}", flush=True)
    else:
        conn.execute("UPDATE outbox SET attempts=?, last_error=?, next_attempt_at=? WHERE id=?",
                     (attempts, error, time.time() + 2 * attempts, row["id"]))
        print(f"[outbox] attempt {attempts}/{constants.MAX_ATTEMPTS} failed for {row['id']}: {error}", flush=True)


def _dispatch_batch(channel) -> None:
    with db.tx() as conn:
        rows = conn.execute(
            "SELECT * FROM outbox WHERE status='new' AND next_attempt_at <= ? ORDER BY created_at LIMIT ?",
            (time.time(), constants.BATCH_SIZE),
        ).fetchall()
    for row in rows:
        with db.tx() as conn:
            try:
                channel.basic_publish(
                    mq_constants.EXCHANGE, row["event_type"], row["payload"],
                    pika.BasicProperties(delivery_mode=2, content_type="application/json", message_id=row["id"]),
                    mandatory=True,
                )  # confirm_delivery() makes this raise unless the broker accepted the message
            except (pika.exceptions.UnroutableError, pika.exceptions.NackError) as e:
                _fail_or_retry(conn, row, f"broker rejected message: {e!r}")
                continue
            conn.execute("UPDATE outbox SET status='sent', attempts=attempts+1, last_error=NULL WHERE id=?", (row["id"],))
            if row["saga_id"]:
                conn.execute("UPDATE saga_log SET state='sent', updated_at=? WHERE saga_id=? AND state='started'",
                             (now(), row["saga_id"]))
        print(f"[outbox] sent event to RabbitMQ: {row['event_type']} {row['id']}", flush=True)


def _broker_down(error) -> None:
    """Broker is unreachable: count one failed attempt for every due event."""
    with db.tx() as conn:
        rows = conn.execute("SELECT * FROM outbox WHERE status='new' AND next_attempt_at <= ?", (time.time(),)).fetchall()
        for row in rows:
            _fail_or_retry(conn, row, f"broker unavailable: {error}")


def run_forever() -> None:
    while not _stop.is_set():
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(settings.rabbit_host, heartbeat=30))
            channel = conn.channel()
            declare(channel)
            channel.confirm_delivery()
            print("[outbox] dispatcher connected to RabbitMQ", flush=True)
            while not _stop.is_set():
                _dispatch_batch(channel)
                conn.process_data_events(time_limit=constants.POLL_SECONDS)
            conn.close()
        except (pika.exceptions.AMQPError, OSError) as e:  # OSError: DNS/TCP errors while the broker is down
            _broker_down(e)
            time.sleep(constants.POLL_SECONDS)


def start() -> None:
    threading.Thread(target=run_forever, daemon=True, name="outbox").start()
