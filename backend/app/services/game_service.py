from dataclasses import dataclass, field
from typing import Dict, Iterable

from app.core.exceptions import AppError
from app.domain.enums import GameStatus, RoleType
from app.schemas.game import GameResult, GameSnapshot
from app.schemas.player import Player
from app.utils.time import utc_now_iso
from app.utils.ids import generate_game_id, generate_player_id


@dataclass
class GameState:
    game_id: str
    players: list[Player] = field(default_factory=list)
    game_status: GameStatus = GameStatus.waiting
    current_round: int = 1
    started: bool = False
    winner_faction: str | None = None
    chats: list[dict[str, object]] = field(default_factory=list)
    votes: list[dict[str, object]] = field(default_factory=list)
    announcements: list[str] = field(default_factory=list)
    owner_player_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    ai_cycle_running: bool = False


_GAMES: Dict[str, GameState] = {}


def _build_ai_players() -> list[Player]:
    return [
        Player(id=generate_player_id(), name="AI-1", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-2", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-3", role=RoleType.unknown, is_ai=True),
        Player(id=generate_player_id(), name="AI-4", role=RoleType.unknown, is_ai=True),
    ]


def _get_game_or_raise(game_id: str) -> GameState:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)
    return game


def _snapshot(game: GameState, player_id: str, my_role: RoleType = RoleType.unknown) -> GameSnapshot:
    return GameSnapshot(
        game_id=game.game_id,
        player_id=player_id,
        game_status=game.game_status,
        current_round=game.current_round,
        started=game.started,
        winner_faction=game.winner_faction,
        players=game.players,
        my_role=my_role,
    )


def _assign_roles(players: Iterable[Player]) -> None:
    roles = [RoleType.wolf, RoleType.prophet]
    roles.extend([RoleType.civilian] * 4)
    for index, player in enumerate(players):
        player.role = roles[index] if index < len(roles) else RoleType.civilian


def create_game(player_name: str) -> GameSnapshot:
    game_id = generate_game_id()
    owner_player_id = generate_player_id()
    players = [Player(id=owner_player_id, name=player_name, role=RoleType.unknown)] + _build_ai_players()
    _GAMES[game_id] = GameState(game_id=game_id, players=players, owner_player_id=owner_player_id)
    return _snapshot(_GAMES[game_id], owner_player_id)


def join_game(game_id: str, player_name: str) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    if game.started:
        raise AppError("游戏已开始，无法加入", status_code=409)

    player_id = generate_player_id()
    game.players.append(Player(id=player_id, name=player_name, role=RoleType.unknown))
    game.announcements.append(f"{player_name} 加入房间")
    return _snapshot(game, player_id)


def get_game(game_id: str) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    return _snapshot(game, game.owner_player_id)


def get_game_state(game_id: str) -> GameState:
    return _get_game_or_raise(game_id)


def set_game_status(game_id: str, status: GameStatus) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    game.game_status = status
    return _snapshot(game, game.owner_player_id)


def advance_round(game_id: str) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    game.current_round += 1
    return _snapshot(game, game.owner_player_id)


def clear_votes(game_id: str) -> None:
    game = _get_game_or_raise(game_id)
    game.votes.clear()


def list_alive_players(game_id: str) -> list[Player]:
    game = _get_game_or_raise(game_id)
    return [player for player in game.players if player.is_alive]


def list_ai_players(game_id: str) -> list[Player]:
    game = _get_game_or_raise(game_id)
    return [player for player in game.players if player.is_ai and player.is_alive]


def start_game(game_id: str) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    if game.started:
        return _snapshot(game, game.owner_player_id)
    if len(game.players) < 2:
        raise AppError("人数不足，无法开局", status_code=409)

    _assign_roles(game.players)
    game.started = True
    game.game_status = GameStatus.speak
    game.announcements.append("游戏开始")
    return _snapshot(game, game.owner_player_id)


def get_player_role(game_id: str, player_id: str) -> RoleType:
    game = _get_game_or_raise(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    return player.role


def record_speak(game_id: str, player_id: str, content: str) -> None:
    game = _get_game_or_raise(game_id)
    if game.game_status not in {GameStatus.speak, GameStatus.day}:
        raise AppError("当前阶段不能发言", status_code=409)
    speaker = next((item for item in game.players if item.id == player_id), None)
    if speaker is None:
        raise AppError("玩家不存在", status_code=404)
    game.chats.append(
        {
            "id": f"chat-{len(game.chats) + 1}",
            "playerId": speaker.id,
            "playerName": speaker.name,
            "content": content,
            "time": utc_now_iso(),
            "isAI": speaker.is_ai,
        }
    )
    game.announcements.append("收到一条发言")


def record_vote(game_id: str, voter_id: str, target_id: str) -> None:
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.vote:
        raise AppError("当前阶段不能投票", status_code=409)
    voter = next((item for item in game.players if item.id == voter_id), None)
    if voter is None:
        raise AppError("玩家不存在", status_code=404)
    game.votes = [vote for vote in game.votes if vote.get("voterId") != voter.id]
    game.votes.append({"voterId": voter.id, "targetId": target_id})
    game.announcements.append("收到一票")


def resolve_vote_round(game_id: str) -> dict[str, object]:
    game = _get_game_or_raise(game_id)
    if not game.votes:
        return {"eliminated": None, "winnerFaction": game.winner_faction}

    tally: dict[str, int] = {}
    for vote in game.votes:
        target_id = str(vote.get("targetId", ""))
        tally[target_id] = tally.get(target_id, 0) + 1

    eliminated_id = max(tally, key=tally.get)
    eliminated_player = next((player for player in game.players if player.id == eliminated_id), None)
    if eliminated_player is not None:
        eliminated_player.is_alive = False
        game.announcements.append(f"{eliminated_player.name} 被投票淘汰")

    game.votes.clear()
    game.current_round += 1

    alive_wolves = sum(1 for player in game.players if player.is_alive and player.role == RoleType.wolf)
    alive_others = sum(1 for player in game.players if player.is_alive and player.role != RoleType.wolf)

    if alive_wolves == 0:
        game.winner_faction = "civilian"
        game.game_status = GameStatus.end
    elif alive_wolves >= alive_others:
        game.winner_faction = "wolf"
        game.game_status = GameStatus.end
    else:
        game.game_status = GameStatus.speak

    return {
        "eliminated": eliminated_player.id if eliminated_player else None,
        "winnerFaction": game.winner_faction,
        "gameStatus": game.game_status,
        "currentRound": game.current_round,
    }


def get_result(game_id: str) -> GameResult:
    game = _get_game_or_raise(game_id)
    return GameResult(
        game_id=game.game_id,
        winner_faction=game.winner_faction or "pending",
        current_round=game.current_round,
        players=game.players,
        chats=game.chats,
        announcements=game.announcements,
    )
