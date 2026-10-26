from fastapi import APIRouter

from src import database as db

router = APIRouter(tags=["outbox"])


@router.get("/outbox")
def list_outbox(user_id: str | None = None):
    with db.tx() as conn:
        rows = conn.execute("SELECT id,saga_id,event_type,status,attempts,last_error,created_at FROM outbox "
                            "WHERE ?1 IS NULL OR payload LIKE '%\"user_id\": \"' || ?1 || '\"%' "
                            "ORDER BY created_at DESC LIMIT 50", (user_id,)).fetchall()
    return {"outbox": [dict(r) for r in rows]}
