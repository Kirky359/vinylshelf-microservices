from src.collection import service


def valid_item(user_id: str, album_id: str) -> dict:
    return service.read_item(user_id, album_id)
