from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from src.security import constants, exceptions, service
from src.security.config import security_settings as settings
from src.security.schemas import Principal

_oidc = f"{settings.oidc_issuer}/protocol/openid-connect"

# Authorization Code flow; it also makes Swagger UI show the "Authorize" button
oauth2_scheme = OAuth2AuthorizationCodeBearer(authorizationUrl=f"{_oidc}/auth", tokenUrl=f"{_oidc}/token",
                                              scopes=constants.SCOPES, auto_error=False)


@lru_cache
def get_verifier() -> service.TokenVerifier:
    return service.TokenVerifier(settings.oidc_issuer, settings.oidc_jwks_url)


async def current_principal(token: str | None = Depends(oauth2_scheme),
                            verifier: service.TokenVerifier = Depends(get_verifier)) -> Principal:
    if not token:
        raise exceptions.MissingToken()
    # PyJWKClient does blocking I/O only on a JWKS cache miss
    return verifier.verify(token)


async def gateway_policy(service_name: str, path: str, request: Request,
                         token: str | None = Depends(oauth2_scheme),
                         verifier: service.TokenVerifier = Depends(get_verifier)) -> Principal | None:
    """Guards the proxy: authentication (valid JWT) + authorization (scope of the route)."""
    scope = service.required_scope(service_name, request.method, path)
    if not settings.auth_enabled or scope is None:
        return None
    if not token:
        raise exceptions.MissingToken()
    principal = verifier.verify(token)
    service.authorize(principal, scope)
    return principal
