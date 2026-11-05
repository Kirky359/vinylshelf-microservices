import json
import re
import uuid

import httpx

CATALOG = {
    "a1": {"id": "a1", "title": "Kind of Blue", "artist": "Miles Davis", "genre": "Jazz", "tracks": 5},
    "a2": {"id": "a2", "title": "Abbey Road", "artist": "The Beatles", "genre": "Rock", "tracks": 17},
}


class FakeVinylShelf:
    """In-memory stand-in of the lab 3 gateway: same URLs and status codes, so the tests need no docker."""

    def __init__(self, fail_completion: bool = False):
        self.users: dict[str, dict] = {}
        self.items: dict[tuple[str, str], dict] = {}
        self.sagas: dict[str, dict] = {}
        self.inbox: list[dict] = []
        self.ratings: list[dict] = []
        self.fail_completion = fail_completion
        self.requests: list[tuple[str, str]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path))
        body = json.loads(request.content) if request.content else {}
        path = request.url.path
        if m := re.fullmatch(r"/auth-service/auth/(register|login)", path):
            return self._auth(m.group(1), body)
        if path == "/catalog-service/catalog/search":
            q = request.url.params.get("q", "").lower()
            return self._json({"items": [a for a in CATALOG.values() if q in json.dumps(a).lower()]})
        if m := re.fullmatch(r"/catalog-service/catalog/albums/([^/]+)", path):
            return self._json(CATALOG[m.group(1)]) if m.group(1) in CATALOG else self._err(404, "album not found")
        if path == "/collection-service/collection/add":
            return self._add(body)
        if m := re.fullmatch(r"/collection-service/collection/([^/]+)/([^/]+)/(progress|complete)", path):
            return self._progress(*m.groups(), body) if m.group(3) == "progress" else self._complete(m.group(1), m.group(2))
        if m := re.fullmatch(r"/collection-service/collection/([^/]+)", path):
            return self._json({"items": [i for (u, _), i in self.items.items() if u == m.group(1)]})
        if m := re.fullmatch(r"/collection-service/saga/([^/]+)", path):
            return self._json(self.sagas[m.group(1)])
        if path == "/rating-service/rating/rate":
            return self._rate(body)
        if m := re.fullmatch(r"/analytics-service/analytics/([^/]+)/dashboard", path):
            return self._dashboard(m.group(1))
        if path == "/analytics-service/analytics/inbox":
            return self._json({"inbox": list(reversed(self.inbox))})
        return self._err(404, "no route " + path)

    @staticmethod
    def _json(data, status=200):
        return httpx.Response(status, json=data)

    def _err(self, status, detail):
        return self._json({"detail": detail}, status)

    def _auth(self, action, body):
        u = body["username"]
        if action == "register":
            self.users[u] = {"id": str(uuid.uuid4()), "password": body["password"]}
            return self._json({"user_id": self.users[u]["id"], "username": u}, 201)
        user = self.users.get(u)
        if not user or user["password"] != body["password"]:
            return self._err(401, "bad credentials")
        return self._json({"token": "t", "user_id": user["id"]})

    def _event(self, name, saga_id=None, status="processed"):
        self.inbox.append({"message_id": str(uuid.uuid4()), "saga_id": saga_id, "event": name, "status": status,
                           "deliveries": 1})

    def _add(self, body):
        key = (body["user_id"], body["album_id"])
        if body["album_id"] not in CATALOG:
            return self._err(404, "album not found in catalog")
        if key in self.items:
            return self._err(409, "album already in collection")
        a = CATALOG[body["album_id"]]
        self.items[key] = {"user_id": key[0], "album_id": a["id"], "title": a["title"], "artist": a["artist"],
                           "genre": a["genre"], "tracks_total": a["tracks"], "tracks_played": 0, "status": "Planned"}
        self._event("collection.album_added")
        return self._json(self.items[key], 201)

    def _progress(self, user, album, _, body):
        item = self.items.get((user, album))
        if not item:
            return self._err(404, "album is not in the collection")
        if not 0 <= body["tracks_played"] <= item["tracks_total"]:
            return self._err(422, "tracks_played out of range")
        item.update(tracks_played=body["tracks_played"], status="Listening" if body["tracks_played"] else "Planned")
        self._event("collection.progress_updated")
        return self._json(item)

    def _complete(self, user, album):
        item = self.items.get((user, album))
        if not item:
            return self._err(404, "album is not in the collection")
        if item["tracks_played"] < item["tracks_total"]:
            return self._err(409, "not all tracks are played yet")
        saga_id = str(uuid.uuid4())
        compensated = self.fail_completion
        self.sagas[saga_id] = {"saga_id": saga_id, "state": "compensated" if compensated else "processed",
                               "reason": "rejected" if compensated else None}
        item["status"] = "Listening" if compensated else "Completed"
        self._event("collection.album_completed", saga_id, "failed" if compensated else "processed")
        return self._json({**item, "status": "CompletionPending", "saga_id": saga_id}, 202)

    def _rate(self, body):
        item = self.items.get((body["user_id"], body["album_id"]))
        if not item or item["status"] not in ("Listening", "Completed"):
            return self._err(409, "only Listening or Completed albums can be rated")
        self.ratings.append(body)
        return self._json({**body, "served_by": "fake"}, 201)

    def _dashboard(self, user):
        done = [i for (u, _), i in self.items.items() if u == user and i["status"] == "Completed"]
        if not self.items:
            return self._err(404, "no statistics for this user yet")
        return self._json({"user_id": user, "albums_completed": len(done), "tracks_played": sum(
            i["tracks_played"] for (u, _), i in self.items.items() if u == user), "average_rating": None,
            "top_genres": [], "top_artists": [], "served_by": "fake"})
