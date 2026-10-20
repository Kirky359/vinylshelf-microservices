from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.discovery import HOSTNAME, call, chain, deregister, register
from app.events import publish

NAME, PORT = "collection-service", 8001


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    yield
    await deregister(instance_id)


app = FastAPI(title="Collection Service (Collection Management)", lifespan=lifespan)

COLLECTIONS: dict[str, dict[str, dict]] = {}  # user_id -> album_id -> AlbumItem


class AddAlbum(BaseModel):
    user_id: str
    album_id: str


class Progress(BaseModel):
    tracks_played: int


def _item(user_id: str, album_id: str) -> dict:
    item = COLLECTIONS.get(user_id, {}).get(album_id)
    if not item:
        raise HTTPException(404, "album is not in the collection")
    return item


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/collection/add", status_code=201)
async def add_album(body: AddAlbum):
    if body.album_id in COLLECTIONS.get(body.user_id, {}):
        raise HTTPException(409, "album already in collection")  # invariant
    # synchronous call: collection-service -> catalog-service (found via Consul)
    r = await call("catalog-service", "GET", f"/catalog/albums/{body.album_id}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, "album not found in catalog")
    album = r.json()
    item = {
        "album_id": album["id"], "title": album["title"], "artist": album["artist"], "genre": album["genre"],
        "tracks_total": album["tracks"], "tracks_played": 0, "status": "Planned",
    }
    COLLECTIONS.setdefault(body.user_id, {})[body.album_id] = item
    publish("collection.album_added", {"user_id": body.user_id, **item})
    return {**item, "metadata_from": album["served_by"], "served_by": HOSTNAME}


@app.post("/collection/{user_id}/{album_id}/progress")
def update_progress(user_id: str, album_id: str, body: Progress):
    item = _item(user_id, album_id)
    if not 0 <= body.tracks_played <= item["tracks_total"]:
        raise HTTPException(422, "tracks_played out of range")
    delta = body.tracks_played - item["tracks_played"]
    item["tracks_played"] = body.tracks_played
    if item["status"] != "Completed" and body.tracks_played > 0:
        item["status"] = "Listening"
    publish("collection.progress_updated", {"user_id": user_id, "album_id": album_id, "tracks_delta": delta,
                                            "genre": item["genre"], "artist": item["artist"]})
    return item


@app.post("/collection/{user_id}/{album_id}/complete")
def complete(user_id: str, album_id: str):
    item = _item(user_id, album_id)
    if item["tracks_played"] < item["tracks_total"]:  # invariant
        raise HTTPException(409, "not all tracks are played yet")
    item["status"] = "Completed"
    publish("collection.album_completed", {"user_id": user_id, "album_id": album_id, "genre": item["genre"],
                                           "artist": item["artist"], "tracks": item["tracks_total"]})
    return item


@app.get("/collection/{user_id}/{album_id}")
def get_item(user_id: str, album_id: str):
    return _item(user_id, album_id)


@app.get("/collection/{user_id}")
def get_collection(user_id: str):
    return {"items": list(COLLECTIONS.get(user_id, {}).values()), "served_by": HOSTNAME}


@app.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(NAME, text, route)
