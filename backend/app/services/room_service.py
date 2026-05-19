from app.schemas.game import GameSnapshot
from app.services.game_service import create_game, get_game, join_game


def create_room(player_name: str) -> GameSnapshot:
    return create_game(player_name)


def join_room(game_id: str, player_name: str) -> GameSnapshot:
    return join_game(game_id, player_name)


def get_room(game_id: str) -> GameSnapshot:
    return get_game(game_id)
