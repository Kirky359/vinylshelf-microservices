from collections.abc import Callable

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from src.gateway.constants import ROUTES
from src.security import constants, exceptions
from src.security.schemas import Principal


class TokenVerifier:
    """Validates a JWT access token: RS256 signature (JWKS), issuer, exp. Authorization is a separate step."""

    def __init__(self, issuer: str, jwks_url: str | None = None, key_provider: Callable[[str], object] | None = None,
                 leeway: int = 10):
        self._issuer = issuer
        self._leeway = leeway
        if key_provider is None:
            client = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

            def key_provider(token: str) -> object:
                return client.get_signing_key_from_jwt(token).key
        self._key_provider = key_provider

    def verify(self, token: str) -> Principal:
        try:
            key = self._key_provider(token)
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self._issuer, leeway=self._leeway,
                                options={"require": ["exp", "iss", "sub"], "verify_aud": False})
        except PyJWKClientConnectionError as exc:
            raise exceptions.AuthServerUnavailable() from exc
        except jwt.ExpiredSignatureError as exc:
            raise exceptions.Unauthorized("token expired") from exc
        except jwt.PyJWTError as exc:
            raise exceptions.Unauthorized("invalid token") from exc
        return Principal(subject=claims["sub"], username=claims.get("preferred_username", claims["sub"]),
                         scopes=frozenset(str(claims.get("scope", "")).split()))


def required_scope(service: str, method: str, path: str) -> str | None:
    """Policy of the gateway: which scope a request needs (None = public). Deny by default:
    every route of a known service needs `<service>:read` (GET/HEAD) or `<service>:write` (everything else)."""
    if service not in ROUTES or (service, path.strip("/")) in constants.PUBLIC_PATHS:
        return None  # unknown services are answered with 404 by the proxy
    action = "read" if method.upper() in constants.READ_METHODS else "write"
    return f"{service.removesuffix('-service')}:{action}"


def authorize(principal: Principal, scope: str) -> None:
    if not principal.has(scope):
        raise exceptions.InsufficientScope(scope)
