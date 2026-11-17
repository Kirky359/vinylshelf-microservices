import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from src.main import app
from src.security.dependencies import get_verifier
from src.security.service import TokenVerifier

ISSUER = "http://localhost:8081/realms/vinylshelf"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(scope="catalog:read", key=_KEY, issuer=ISSUER, ttl=300, sub="user-1"):
    now = int(time.time())
    claims = {"sub": sub, "preferred_username": "artem", "iss": issuer, "iat": now, "exp": now + ttl, "scope": scope}
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture
def client(monkeypatch):
    verifier = TokenVerifier(ISSUER, key_provider=lambda token: _KEY.public_key())
    app.dependency_overrides[get_verifier] = lambda: verifier
    sent = {}

    async def fake_call(name, method, path, **kwargs):
        import httpx
        sent.update(name=name, method=method, path=path, headers=kwargs["headers"])
        return httpx.Response(200, json={"ok": True}, headers={"access-control-allow-origin": "*"})

    monkeypatch.setattr("src.gateway.service.call", fake_call)
    c = TestClient(app)
    c.sent = sent
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_key():
    return _OTHER_KEY
