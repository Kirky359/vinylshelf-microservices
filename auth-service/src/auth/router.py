from fastapi import APIRouter

from src.auth import service
from src.auth.schemas import Credentials, LoginResponse, RegisteredUser
from src.discovery import HOSTNAME

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=RegisteredUser)
def register_user(c: Credentials):
    user = service.register_user(c)
    return {"user_id": user["id"], "username": c.username, "served_by": HOSTNAME}


@router.post("/login", response_model=LoginResponse)
def login(c: Credentials):
    token, user_id = service.login(c)
    return {"token": token, "user_id": user_id, "served_by": HOSTNAME}
