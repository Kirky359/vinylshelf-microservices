import os
import sqlite3
from contextlib import contextmanager

from src.config import settings


@contextmanager
def tx():
    """One local transaction: commit on success, roll back on any exception."""
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init(schema: str) -> None:
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    with tx() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(schema)
