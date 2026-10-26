import hashlib
import secrets
import uuid

from src.auth import exceptions, models
from src.auth.schemas import Credentials
from src.messaging.broker import publish


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def register_user(c: Credentials) -> dict:
    if c.username in models.USERS:
        raise exceptions.UsernameTaken()
    salt = secrets.token_hex(8)
    user = {"id": str(uuid.uuid4()), "username": c.username, "salt": salt, "hash": _hash(c.password, salt)}
    models.USERS[c.username] = user
    publish("user.registered", {"user_id": user["id"], "username": c.username})
    return user


def login(c: Credentials) -> tuple[str, str]:
    """Returns (token, user_id)."""
    user = models.USERS.get(c.username)
    if not user or user["hash"] != _hash(c.password, user["salt"]):
        raise exceptions.BadCredentials()
    token = secrets.token_urlsafe(16)
    models.TOKENS[token] = user["id"]
    return token, user["id"]
