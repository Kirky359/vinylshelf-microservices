from fastapi import APIRouter, Depends

from src.security.dependencies import current_principal
from src.security.schemas import Me, Principal

router = APIRouter(tags=["security"])


@router.get("/me", response_model=Me)
async def me(principal: Principal = Depends(current_principal)):
    """Claims of the verified access token (any valid token is enough)."""
    return {"sub": principal.subject, "username": principal.username, "scopes": sorted(principal.scopes)}
