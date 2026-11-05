"""Background workers of the SAGA: DLQ listener and timeout/failed-outbox watchdog."""
import json
import threading
import time
from datetime import datetime

import pika

from src import database as db
from src.config import settings
from src.messaging import constants as mq_constants
from src.messaging.broker import declare
from src.saga import exceptions
from src.saga.config import SagaConfig
from src.saga.repository import SagaRepository
from src.saga.service import SagaService


class SagaCoordinator:
    def __init__(self, saga: SagaService, config: SagaConfig):
        self.saga = saga
        self.config = config
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._listen_dlq, daemon=True, name="saga-dlq").start()
        threading.Thread(target=self._watchdog, daemon=True, name="saga-watchdog").start()

    def stop(self) -> None:
        self._stop.set()

    def check_timeouts_and_failed_outbox(self) -> None:
        timeout = self.config.saga_timeout_seconds
        cutoff = time.time() - timeout
        with db.tx() as conn:
            sagas = SagaRepository(conn)
            stale = [r["saga_id"] for r in sagas.list_unfinished() if self._age_ts(r["updated_at"]) < cutoff]
            failed = sagas.list_with_failed_outbox_ids()
        for saga_id in failed:
            print(f"[saga] outbox event of {saga_id} failed, rolling back...", flush=True)
            self.saga.compensate(saga_id, "outbox delivery failed")
        for saga_id in stale:
            print(f"[saga] timeout for saga {saga_id}, performing rollback...", flush=True)
            self.saga.compensate(saga_id, f"timeout {timeout:.0f}s")

    def _listen_dlq(self) -> None:
        while not self._stop.is_set():
            try:
                conn = pika.BlockingConnection(pika.ConnectionParameters(settings.rabbit_host, heartbeat=30))
                ch = conn.channel()
                declare(ch)
                ch.basic_consume(mq_constants.DLQ, self._on_dead_letter)
                print("[saga] coordinator listens to DLQ", flush=True)
                while not self._stop.is_set():
                    conn.process_data_events(time_limit=1)
                conn.close()
            except (pika.exceptions.AMQPError, OSError) as e:
                print(f"[saga] broker not ready: {e!r}", flush=True)
                time.sleep(2)
            except Exception as e:  # keep the coordinator alive
                print(f"[saga] error: {e!r}", flush=True)
                time.sleep(2)

    def _on_dead_letter(self, ch, method, properties, body) -> None:
        event = json.loads(body)
        deaths = (properties.headers or {}).get("x-death", [])
        reason = deaths[0].get("reason", "unknown") if deaths else "unknown"
        saga_id = event.get("saga_id")
        if saga_id and event.get("event") == "collection.album_completed":
            print(f"[saga] DLQ received {event['event']} for saga {saga_id} (reason: {reason})", flush=True)
            try:
                self.saga.compensate(saga_id, f"dead-lettered ({reason})")
            except exceptions.SagaNotFound:
                print(f"[saga] unknown saga {saga_id}, ignored", flush=True)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def _watchdog(self) -> None:
        """Independent of the broker: it must work exactly when RabbitMQ is down or silent."""
        while not self._stop.is_set():
            try:
                self.check_timeouts_and_failed_outbox()
            except Exception as e:
                print(f"[saga] watchdog error: {e!r}", flush=True)
            time.sleep(1)

    @staticmethod
    def _age_ts(iso: str) -> float:
        return datetime.fromisoformat(iso).timestamp()
