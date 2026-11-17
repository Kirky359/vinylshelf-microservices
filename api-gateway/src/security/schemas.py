from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    """Who is calling: the verified claims of the access token."""
    model_config = ConfigDict(frozen=True)

    subject: str
    username: str
    scopes: frozenset[str]

    def has(self, scope: str) -> bool:
        return scope in self.scopes


class Me(BaseModel):
    sub: str
    username: str
    scopes: list[str]
