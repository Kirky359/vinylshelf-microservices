import json
import threading
from pathlib import Path
from typing import Any


class JsonLogFile:
    """Small helper: keeps a JSON document on disk up to date (used for token and injection logs)."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def write(self, document: Any) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(document, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def read(self, default: Any) -> Any:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default
