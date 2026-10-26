from src.analytics import exceptions, models
from src.analytics.config import analytics_settings
from src.discovery import HOSTNAME

_completed_seen = 0


def handle(event: dict) -> None:
    global _completed_seen
    kind, uid = event["event"], event.get("user_id")
    if kind == "collection.album_completed":
        _completed_seen += 1
        if analytics_settings.fail_every_n and _completed_seen % analytics_settings.fail_every_n == 0:
            raise RuntimeError("Simulated processing error")
    models.LOG.appendleft({"handled_by": HOSTNAME, **event})
    s = models.STATS[uid]
    if kind == "collection.progress_updated":
        s["tracks_played"] += max(event["tracks_delta"], 0)
    elif kind == "collection.album_completed":
        s["albums_completed"] += 1
        s["genres"][event["genre"]] += 1
        s["artists"][event["artist"]] += 1
    elif kind == "rating.created":
        s["ratings"].append(event["rating"])


def dashboard(user_id: str) -> dict:
    if user_id not in models.STATS:
        raise exceptions.NoStatistics()
    s = models.STATS[user_id]
    avg = round(sum(s["ratings"]) / len(s["ratings"]), 2) if s["ratings"] else None
    return {"user_id": user_id, "albums_completed": s["albums_completed"], "tracks_played": s["tracks_played"],
            "average_rating": avg, "top_genres": s["genres"].most_common(3),
            "top_artists": s["artists"].most_common(3), "served_by": HOSTNAME}
