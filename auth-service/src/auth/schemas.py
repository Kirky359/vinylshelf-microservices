from pydantic import BaseModel


class Credentials(BaseModel):
    username: str
    password: str


class RegisteredUser(BaseModel):
    user_id: str
    username: str
    served_by: str


class LoginResponse(BaseModel):
    token: str
    user_id: str
    served_by: str
