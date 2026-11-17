from tests.conftest import ISSUER, make_token


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401(client):
    r = client.get("/catalog-service/catalog/search")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_valid_token_with_scope_passes_and_identity_is_forwarded(client):
    r = client.get("/catalog-service/catalog/search", headers=bearer(make_token("openid catalog:read")))
    assert r.status_code == 200
    assert client.sent["headers"]["x-user-id"] == "user-1"
    assert client.sent["headers"]["x-user-scopes"] == "catalog:read openid"


def test_client_cannot_spoof_identity_headers(client):
    client.get("/catalog-service/catalog/search",
               headers={**bearer(make_token("catalog:read")), "X-User-Id": "someone-else"})
    assert client.sent["headers"]["x-user-id"] == "user-1"


def test_missing_scope_is_403(client):
    r = client.post("/collection-service/collection/add", headers=bearer(make_token("collection:read")), json={})
    assert r.status_code == 403
    assert 'scope="collection:write"' in r.headers["www-authenticate"]


def test_scopes_are_per_service_and_per_method(client):
    token = bearer(make_token("collection:read collection:write"))
    assert client.get("/collection-service/collection/u1", headers=token).status_code == 200
    assert client.post("/collection-service/collection/add", headers=token, json={}).status_code == 200
    assert client.post("/rating-service/rating/rate", headers=token, json={}).status_code == 403
    assert client.get("/analytics-service/analytics/u1/dashboard", headers=token).status_code == 403


def test_expired_token_is_401(client):
    r = client.get("/catalog-service/catalog/search", headers=bearer(make_token(ttl=-60)))
    assert r.status_code == 401 and "expired" in r.json()["detail"]


def test_token_signed_with_foreign_key_is_401(client, other_key):
    r = client.get("/catalog-service/catalog/search", headers=bearer(make_token(key=other_key)))
    assert r.status_code == 401


def test_wrong_issuer_is_401(client):
    r = client.get("/catalog-service/catalog/search", headers=bearer(make_token(issuer="http://evil/realms/x")))
    assert r.status_code == 401


def test_alg_none_token_is_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "x", "iss": ISSUER, "exp": 9999999999, "scope": "catalog:read"}, None, algorithm="none")
    assert client.get("/catalog-service/catalog/search", headers=bearer(forged)).status_code == 401


def test_public_paths_need_no_token(client):
    assert client.get("/health").status_code == 200
    assert client.post("/auth-service/auth/login", json={}).status_code == 200
    assert client.get("/unknown-service/x").status_code == 404


def test_me_returns_claims(client):
    r = client.get("/me", headers=bearer(make_token("openid collection:read")))
    assert r.json() == {"sub": "user-1", "username": "artem", "scopes": ["collection:read", "openid"]}


def test_cors_preflight_for_allowed_origin(client):
    r = client.options("/collection-service/collection/add", headers={
        "Origin": "https://cad.kpi.ua", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://cad.kpi.ua"
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_cors_blocks_other_origin_and_is_not_overwritten_by_service(client):
    r = client.options("/catalog-service/catalog/search", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 400
    r = client.get("/catalog-service/catalog/search", headers={**bearer(make_token()), "Origin": "https://cad.kpi.ua"})
    # the mocked service answered with ACAO "*": the gateway must not pass it through
    assert r.headers["access-control-allow-origin"] == "https://cad.kpi.ua"
