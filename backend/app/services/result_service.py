from app.services.game_service import get_result


def fetch_result(game_id: str):
    return get_result(game_id)
