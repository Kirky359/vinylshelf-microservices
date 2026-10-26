from collections import Counter, defaultdict, deque

# in-memory read model (the dashboard) and the event log
STATS = defaultdict(lambda: {"albums_completed": 0, "tracks_played": 0, "ratings": [],
                             "genres": Counter(), "artists": Counter()})
LOG: deque = deque(maxlen=50)
