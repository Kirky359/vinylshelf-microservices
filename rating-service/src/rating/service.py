from fastapi.concurrency import run_in_threadpool

from src.discovery import call
from src.messaging.broker import publish
from src.rating import constants, exceptions, models
from src.rating.schemas import Rate


async def rate(body: Rate) -> None:
    # synchronous call: rating-service -> collection-service (invariant: only Listening/Completed albums)
    r = await call("collection-service", "GET", f"/collection/{body.user_id}/{body.album_id}")
    if r.status_code != 200:
        raise exceptions.NotInCollection()
    item = r.json()
    if item["status"] not in constants.RATABLE_STATUSES:
        raise exceptions.NotRatable()
    models.RATINGS[(body.user_id, body.album_id)] = body.rating
    # publish() is blocking (pika), so keep it off the event loop
    await run_in_threadpool(publish, "rating.created", {
        "user_id": body.user_id, "album_id": body.album_id, "rating": body.rating,
        "genre": item["genre"], "artist": item["artist"]})


def list_ratings(user_id: str) -> dict[str, int]:
    return {a: v for (u, a), v in models.RATINGS.items() if u == user_id}
