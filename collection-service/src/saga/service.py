"""SAGA orchestrator for 'complete album': timeouts, DLQ listener and compensation."""
import json
import threading
import time
import uuid
from datetime import datetime

import pika

from src import database as db
from src.config import settings
from src.messaging import constants as mq_constants
from src.messaging.broker import declare
from src.outbox import service as outbox_service
from src.saga import exceptions
from src.saga.config import saga_settings
from src.saga.constants import FINAL_STATES, State
from src.utils import now

_stop = threading.Event()


def stop() -> None:
    _stop.set()


def start_saga(conn, user_id: str, album_id: str, prev_status: str) -> str:
    """Local transaction #1 of the saga: status -> CompletionPending + saga_log (+ outbox event, added by the caller)."""
    saga_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO saga_log (saga_id,user_id,album_id,prev_status,state,started_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (saga_id, user_id, album_id, prev_status, State.STARTED, now(), now()),
    )
    conn.execute("UPDATE collection_items SET status='CompletionPending' WHERE user_id=? AND album_id=?", (user_id, album_id))
    return saga_id


def get_saga(conn, saga_id: str):
    saga = conn.execute("SELECT * FROM saga_log WHERE saga_id=?", (saga_id,)).fetchone()
    if saga is None:
        raise exceptions.SagaNotFound()
    return saga


def confirm(saga_id: str) -> str:
    """Consumer confirmed processing: finish the saga. Idempotent. Returns resulting state."""
    with db.tx() as conn:
        saga = get_saga(conn, saga_id)
        if saga["state"] in FINAL_STATES:
            return saga["state"]
        conn.execute("UPDATE collection_items SET status='Completed' WHERE user_id=? AND album_id=? AND status='CompletionPending'",
                     (saga["user_id"], saga["album_id"]))
        conn.execute("UPDATE saga_log SET state='processed', updated_at=? WHERE saga_id=?", (now(), saga_id))
    print(f"[saga] {saga_id} confirmed by consumer -> processed", flush=True)
    return State.PROCESSED


def compensate(saga_id: str, reason: str) -> str:
    """Compensating transaction: undo the status change. Idempotent. Returns resulting state."""
    with db.tx() as conn:
        saga = get_saga(conn, saga_id)
        if saga["state"] in FINAL_STATES:
            return saga["state"]
        conn.execute("UPDATE collection_items SET status=? WHERE user_id=? AND album_id=? AND status='CompletionPending'",
                     (saga["prev_status"], saga["user_id"], saga["album_id"]))
        conn.execute("UPDATE saga_log SET state='compensated', reason=?, updated_at=? WHERE saga_id=?",
                     (reason, now(), saga_id))
        outbox_service.add_event(conn, "collection.album_completion_cancelled",
                                 {"user_id": saga["user_id"], "album_id": saga["album_id"], "reason": reason}, saga_id)
    print(f"[saga] {saga_id} compensated, status restored to {saga['prev_status']}: {reason}", flush=True)
    return State.COMPENSATED


def find_pending(user_id: str, album_id: str) -> str:
    with db.tx() as conn:
        row = conn.execute("SELECT saga_id FROM saga_log WHERE user_id=? AND album_id=? AND state IN ('started','sent') "
                           "ORDER BY started_at DESC LIMIT 1", (user_id, album_id)).fetchone()
    if not row:
        raise exceptions.NoPendingSaga()
    return row["saga_id"]


def read_saga(saga_id: str) -> dict:
    with db.tx() as conn:
        return dict(get_saga(conn, saga_id))


def list_sagas(user_id: str | None) -> list[dict]:
    with db.tx() as conn:
        rows = conn.execute("SELECT * FROM saga_log WHERE ?1 IS NULL OR user_id=?1 ORDER BY started_at DESC LIMIT 50", (user_id,))
        return [dict(r) for r in rows]


def _age_ts(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def check_timeouts_and_failed_outbox() -> None:
    timeout = saga_settings.saga_timeout_seconds
    cutoff = time.time() - timeout
    with db.tx() as conn:
        stale = [r["saga_id"] for r in conn.execute("SELECT saga_id, updated_at FROM saga_log WHERE state IN ('started','sent')")
                 if _age_ts(r["updated_at"]) < cutoff]
        failed = [r["saga_id"] for r in conn.execute(
            "SELECT o.saga_id FROM outbox o JOIN saga_log s ON s.saga_id=o.saga_id "
            "WHERE o.status='failed' AND o.event_type='collection.album_completed' AND s.state IN ('started','sent')")]
    for saga_id in failed:
        print(f"[saga] outbox event of {saga_id} failed, rolling back...", flush=True)
        compensate(saga_id, "outbox delivery failed")
    for saga_id in stale:
        print(f"[saga] timeout for saga {saga_id}, performing rollback...", flush=True)
        compensate(saga_id, f"timeout {timeout:.0f}s")


def _on_dead_letter(ch, method, properties, body):
    event = json.loads(body)
    deaths = (properties.headers or {}).get("x-death", [])
    reason = deaths[0].get("reason", "unknown") if deaths else "unknown"
    saga_id = event.get("saga_id")
    if saga_id and event.get("event") == "collection.album_completed":
        print(f"[saga] DLQ received {event['event']} for saga {saga_id} (reason: {reason})", flush=True)
        try:
            compensate(saga_id, f"dead-lettered ({reason})")
        except exceptions.SagaNotFound:
            print(f"[saga] unknown saga {saga_id}, ignored", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def run_forever() -> None:
    while not _stop.is_set():
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(settings.rabbit_host, heartbeat=30))
            ch = conn.channel()
            declare(ch)
            ch.basic_consume(mq_constants.DLQ, _on_dead_letter)
            print("[saga] coordinator listens to DLQ", flush=True)
            while not _stop.is_set():
                conn.process_data_events(time_limit=1)
            conn.close()
        except (pika.exceptions.AMQPError, OSError) as e:
            print(f"[saga] broker not ready: {e!r}", flush=True)
            time.sleep(2)
        except Exception as e:  # keep the coordinator alive
            print(f"[saga] error: {e!r}", flush=True)
            time.sleep(2)


def watchdog() -> None:
    """Independent of the broker: it must work exactly when RabbitMQ is down or silent."""
    while not _stop.is_set():
        try:
            check_timeouts_and_failed_outbox()
        except Exception as e:
            print(f"[saga] watchdog error: {e!r}", flush=True)
        time.sleep(1)


def start() -> None:
    threading.Thread(target=run_forever, daemon=True, name="saga-dlq").start()
    threading.Thread(target=watchdog, daemon=True, name="saga-watchdog").start()
