from app.schemas.game import GameSnapshot
from app.services.game_service import create_game, get_game, join_game, start_game


def create_room(player_name: str) -> GameSnapshot:
    return create_game(player_name)


def join_room(game_id: str, player_name: str) -> GameSnapshot:
    return join_game(game_id, player_name)


def get_room(game_id: str, requester_id: str | None = None) -> GameSnapshot:
    return get_game(game_id, requester_id)


def start_room(game_id: str) -> GameSnapshot:
    snapshot = start_game(game_id)
    from app.services.ai_service import launch_ai_cycle
    launch_ai_cycle(game_id)
    return snapshot
