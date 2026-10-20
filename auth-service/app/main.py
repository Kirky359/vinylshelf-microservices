from contextlib import asynccontextmanager
import hashlib
import secrets
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.discovery import HOSTNAME, chain, deregister, register
from app.events import publish

NAME, PORT = "auth-service", 8000


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    yield
    await deregister(instance_id)


app = FastAPI(title="Auth Service (User Management)", lifespan=lifespan)

USERS: dict[str, dict] = {}   # username -> user
TOKENS: dict[str, str] = {}   # token -> user_id


class Credentials(BaseModel):
    username: str
    password: str


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register_user(c: Credentials):
    if c.username in USERS:
        raise HTTPException(409, "username taken")
    salt = secrets.token_hex(8)
    user = {"id": str(uuid.uuid4()), "username": c.username, "salt": salt, "hash": _hash(c.password, salt)}
    USERS[c.username] = user
    publish("user.registered", {"user_id": user["id"], "username": c.username})
    return {"user_id": user["id"], "username": c.username, "served_by": HOSTNAME}


@app.post("/auth/login")
def login(c: Credentials):
    user = USERS.get(c.username)
    if not user or user["hash"] != _hash(c.password, user["salt"]):
        raise HTTPException(401, "bad credentials")
    token = secrets.token_urlsafe(16)
    TOKENS[token] = user["id"]
    return {"token": token, "user_id": user["id"], "served_by": HOSTNAME}


@app.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(NAME, text, route)
