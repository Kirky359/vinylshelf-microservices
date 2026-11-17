import base64
import json

import httpx
import pytest

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import ApiError
from vinyl_agents.vinylshelf.client import VinylShelfClient


def _jwt(sub: str) -> str:
    def part(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part({'sub': sub})}.sig"


async def test_keycloak_login_sets_bearer_token(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    real_client = httpx.AsyncClient

    class FakeKeycloak(real_client):
        async def post(self, url, data=None, **kw):
            assert data["client_id"] == "vinylshelf-cli" and data["grant_type"] == "password"
            return httpx.Response(200, json={"access_token": _jwt("user-42")})

    monkeypatch.setattr("vinyl_agents.vinylshelf.client.httpx.AsyncClient", FakeKeycloak)
    settings = Settings(_env_file=None, keycloak_token_url="http://kc/token")
    client = VinylShelfClient(settings, httpx.MockTransport(handler))
    assert (await client.login("artem", "x"))["user_id"] == "user-42"
    await client._request("GET", "/catalog-service/catalog/search")
    assert seen["auth"] == f"Bearer {_jwt('user-42')}"


async def test_keycloak_rejects_credentials(monkeypatch):
    class FakeKeycloak(httpx.AsyncClient):
        async def post(self, url, data=None, **kw):
            return httpx.Response(401, json={})

    monkeypatch.setattr("vinyl_agents.vinylshelf.client.httpx.AsyncClient", FakeKeycloak)
    client = VinylShelfClient(Settings(_env_file=None, keycloak_token_url="http://kc/token"),
                              httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ApiError):
        await client.login("artem", "bad")
