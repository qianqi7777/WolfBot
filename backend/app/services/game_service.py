from dataclasses import dataclass, field
from typing import Dict

from app.core.exceptions import AppError
from app.domain.enums import GameStatus, RoleType
from app.schemas.game import GameResult, GameSnapshot
from app.schemas.player import Player
from app.utils.ids import generate_game_id, generate_player_id


@dataclass
class GameState:
    game_id: str
    players: list[Player] = field(default_factory=list)
    game_status: GameStatus = GameStatus.waiting
    chats: list[dict[str, str]] = field(default_factory=list)
    votes: list[dict[str, str]] = field(default_factory=list)
    announcements: list[str] = field(default_factory=list)
    owner_player_id: str = ""


_GAMES: Dict[str, GameState] = {}


def _build_ai_players() -> list[Player]:
    return [
        Player(id=generate_player_id(), name="AI-1", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-2", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-3", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-4", role=RoleType.unknown, is_ai=True),
    ]


def create_game(player_name: str) -> GameSnapshot:
    game_id = generate_game_id()
    owner_player_id = generate_player_id()
    players = [Player(id=owner_player_id, name=player_name, role=RoleType.unknown)] + _build_ai_players()
    _GAMES[game_id] = GameState(game_id=game_id, players=players, owner_player_id=owner_player_id)
    return GameSnapshot(game_id=game_id, player_id=owner_player_id, game_status=GameStatus.waiting, players=players)


def join_game(game_id: str, player_name: str) -> GameSnapshot:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)

    player_id = generate_player_id()
    game.players.append(Player(id=player_id, name=player_name, role=RoleType.unknown))
    return GameSnapshot(game_id=game.game_id, player_id=player_id, game_status=game.game_status, players=game.players)


def get_game(game_id: str) -> GameSnapshot:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)

    return GameSnapshot(
        game_id=game.game_id,
        player_id=game.owner_player_id,
        game_status=game.game_status,
        players=game.players,
    )


def record_speak(game_id: str, content: str) -> None:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)
    game.chats.append({"content": content})


def record_vote(game_id: str, target_id: str) -> None:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)
    game.votes.append({"target_id": target_id})


def get_result(game_id: str) -> GameResult:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)
    return GameResult(winner_faction="pending", players=game.players)
