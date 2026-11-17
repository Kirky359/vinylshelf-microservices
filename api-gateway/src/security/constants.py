# OAuth scopes -> what they allow. Keycloak client scopes have exactly these names (keycloak/vinylshelf-realm.json).
SCOPES = {
    "catalog:read": "Read the album catalog",
    "collection:read": "Read the user's collection and SAGA state",
    "collection:write": "Add albums, update progress, complete albums",
    "rating:read": "Read the user's ratings",
    "rating:write": "Rate albums",
    "analytics:read": "Read the analytics dashboard and inbox",
}

READ_METHODS = {"GET", "HEAD"}

# (service, path) pairs that need no token: the legacy login/register of lab 2
PUBLIC_PATHS = {("auth-service", "auth/login"), ("auth-service", "auth/register")}
