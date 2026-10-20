from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.discovery import HOSTNAME, chain, deregister, register

NAME, PORT = "catalog-service", 8004


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    yield
    await deregister(instance_id)


app = FastAPI(title="Catalog Service (Search & Metadata)", lifespan=lifespan)

ALBUMS = {
    "a1": {"id": "a1", "title": "Kind of Blue", "artist": "Miles Davis", "genre": "Jazz", "tracks": 5},
    "a2": {"id": "a2", "title": "Abbey Road", "artist": "The Beatles", "genre": "Rock", "tracks": 17},
    "a3": {"id": "a3", "title": "What's Going On", "artist": "Marvin Gaye", "genre": "Soul", "tracks": 9},
    "a4": {"id": "a4", "title": "Blue Train", "artist": "John Coltrane", "genre": "Jazz", "tracks": 5},
    "a5": {"id": "a5", "title": "The Dark Side of the Moon", "artist": "Pink Floyd", "genre": "Rock", "tracks": 10},
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalog/search")
def search(q: str = ""):
    q = q.lower()
    items = [a for a in ALBUMS.values() if q in a["title"].lower() or q in a["artist"].lower() or q in a["genre"].lower()]
    return {"items": items, "served_by": HOSTNAME}


@app.get("/catalog/albums/{album_id}")
def get_album(album_id: str):
    if album_id not in ALBUMS:
        raise HTTPException(404, "album not found")
    return {**ALBUMS[album_id], "served_by": HOSTNAME}


@app.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(NAME, text, route)
