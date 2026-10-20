from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.discovery import HOSTNAME, call, chain, deregister, register
from app.events import publish

NAME, PORT = "rating-service", 8002


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    yield
    await deregister(instance_id)


app = FastAPI(title="Rating Service (Rating Management)", lifespan=lifespan)

RATINGS: dict[tuple[str, str], int] = {}


class Rate(BaseModel):
    user_id: str
    album_id: str
    rating: int = Field(ge=1, le=10)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/rating/rate", status_code=201)
async def rate(body: Rate):
    # synchronous call: rating-service -> collection-service (invariant: only Listening/Completed albums)
    r = await call("collection-service", "GET", f"/collection/{body.user_id}/{body.album_id}")
    if r.status_code != 200:
        raise HTTPException(404, "album is not in the user's collection")
    item = r.json()
    if item["status"] not in ("Listening", "Completed"):
        raise HTTPException(409, "album can be rated only when listening or completed")
    RATINGS[(body.user_id, body.album_id)] = body.rating
    publish("rating.created", {"user_id": body.user_id, "album_id": body.album_id, "rating": body.rating,
                               "genre": item["genre"], "artist": item["artist"]})
    return {"user_id": body.user_id, "album_id": body.album_id, "rating": body.rating, "served_by": HOSTNAME}


@app.get("/rating/{user_id}")
def list_ratings(user_id: str):
    return {"ratings": {a: v for (u, a), v in RATINGS.items() if u == user_id}}


@app.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(NAME, text, route)
