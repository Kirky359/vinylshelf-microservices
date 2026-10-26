from src.catalog import service


def valid_album(album_id: str) -> dict:
    return service.get_album(album_id)
