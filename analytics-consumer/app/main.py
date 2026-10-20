import json
from contextlib import asynccontextmanager
import threading
import time
from collections import Counter, defaultdict, deque

import pika
from fastapi import FastAPI, HTTPException

from app.discovery import HOSTNAME, chain, deregister, register
from app.events import QUEUE, RABBIT_HOST, declare

NAME, PORT = "analytics-service", 8005

STATS = defaultdict(lambda: {"albums_completed": 0, "tracks_played": 0, "ratings": [],
                             "genres": Counter(), "artists": Counter()})
LOG: deque = deque(maxlen=50)
_stop = threading.Event()


def handle(event: dict) -> None:
    kind, uid = event["event"], event.get("user_id")
    LOG.appendleft({"handled_by": HOSTNAME, **event})
    s = STATS[uid]
    if kind == "collection.progress_updated":
        s["tracks_played"] += max(event["tracks_delta"], 0)
    elif kind == "collection.album_completed":
        s["albums_completed"] += 1
        s["genres"][event["genre"]] += 1
        s["artists"][event["artist"]] += 1
    elif kind == "rating.created":
        s["ratings"].append(event["rating"])


def callback(ch, method, properties, body):
    event = json.loads(body)
    print(f"[analytics] received {event['event']}: {event}", flush=True)
    handle(event)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_forever() -> None:
    while not _stop.is_set():
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
            ch = conn.channel()
            declare(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(QUEUE, callback)
            print("[analytics] waiting for events...", flush=True)
            while not _stop.is_set():
                conn.process_data_events(time_limit=1)
            conn.close()
        except pika.exceptions.AMQPError as exc:
            print(f"[analytics] broker not ready: {exc}", flush=True)
            time.sleep(2)


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    threading.Thread(target=consume_forever, daemon=True).start()
    yield
    _stop.set()
    await deregister(instance_id)


app = FastAPI(title="Analytics Service (consumer + dashboard)", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/analytics/{user_id}/dashboard")
def dashboard(user_id: str):
    if user_id not in STATS:
        raise HTTPException(404, "no statistics for this user yet (or they live on another consumer instance)")
    s = STATS[user_id]
    avg = round(sum(s["ratings"]) / len(s["ratings"]), 2) if s["ratings"] else None
    return {"user_id": user_id, "albums_completed": s["albums_completed"], "tracks_played": s["tracks_played"],
            "average_rating": avg, "top_genres": s["genres"].most_common(3),
            "top_artists": s["artists"].most_common(3), "served_by": HOSTNAME}


@app.get("/analytics/events/log")
def events_log():
    return {"handled_by": HOSTNAME, "events": list(LOG)}


@app.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(NAME, text, route)
