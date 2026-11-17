from pydantic_settings import BaseSettings


class SecurityConfig(BaseSettings):
    """OAuth 2.0 / OpenID Connect (Keycloak)."""
    auth_enabled: bool = True
    # issuer = what Keycloak writes into the "iss" claim and what browsers open (public URL)
    oidc_issuer: str = "http://localhost:8081/realms/vinylshelf"
    # JWKS is fetched by the gateway container over the internal network
    oidc_jwks_url: str = "http://keycloak:8080/realms/vinylshelf/protocol/openid-connect/certs"
    swagger_client_id: str = "vinylshelf-web"


security_settings = SecurityConfig()
