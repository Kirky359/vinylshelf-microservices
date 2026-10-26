from pydantic import BaseModel


class SagaRef(BaseModel):
    saga_id: str


class RollbackRequest(BaseModel):
    user_id: str
    album_id: str
