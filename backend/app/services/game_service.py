from dataclasses import dataclass, field
import random
from typing import Dict, Iterable

from app.core.exceptions import AppError
from app.domain.enums import GameStatus, RoleType
from app.schemas.game import AiConfigView, GameResult, GameSnapshot, RoomSettings, RoomSettingsUpdate, SceneConfig
from app.schemas.player import Player
from app.utils.time import utc_now_iso
from app.utils.ids import generate_game_id, generate_player_id


@dataclass
class AiRuntimeConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 20.0
    temperature: float = 0.7
    enable_mock: bool = True


@dataclass
class RoomRuntimeSettings:
    scene: SceneConfig
    ai: AiRuntimeConfig


def _default_scene() -> SceneConfig:
    return SceneConfig()


def _default_ai_runtime() -> AiRuntimeConfig:
    from app.core.config import settings

    return AiRuntimeConfig(
        base_url=settings.ai_api_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
        temperature=settings.ai_temperature,
        enable_mock=settings.ai_enable_mock,
    )


def _default_room_settings() -> RoomRuntimeSettings:
    return RoomRuntimeSettings(scene=_default_scene(), ai=_default_ai_runtime())


@dataclass
class GameState:
    game_id: str
    players: list[Player] = field(default_factory=list)
    game_status: GameStatus = GameStatus.waiting
    current_round: int = 1
    current_speaker_id: str | None = None
    started: bool = False
    winner_faction: str | None = None
    chats: list[dict[str, object]] = field(default_factory=list)
    votes: list[dict[str, object]] = field(default_factory=list)
    announcements: list[str] = field(default_factory=list)
    owner_player_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    ai_cycle_running: bool = False
    night_actions: list[dict[str, object]] = field(default_factory=list)
    speak_order: list[str] = field(default_factory=list)
    speak_turn_submitted: bool = False
    room_settings: RoomRuntimeSettings = field(default_factory=_default_room_settings)


_GAMES: Dict[str, GameState] = {}


def _build_ai_players(count: int) -> list[Player]:
    return [
        Player(id=generate_player_id(), name=f"AI-{index + 1}", role=RoleType.unknown, is_ai=True)
        for index in range(count)
    ]


def _get_game_or_raise(game_id: str) -> GameState:
    game = _GAMES.get(game_id)
    if game is None:
        raise AppError("房间不存在", status_code=404)
    return game


def _room_settings_view(settings: RoomRuntimeSettings) -> RoomSettings:
    return RoomSettings(
        scene=settings.scene,
        ai=AiConfigView(
            base_url=settings.ai.base_url,
            model=settings.ai.model,
            timeout_seconds=settings.ai.timeout_seconds,
            temperature=settings.ai.temperature,
            enable_mock=settings.ai.enable_mock,
            has_api_key=bool(settings.ai.api_key),
        ),
    )


def _snapshot(game: GameState, player_id: str, my_role: RoleType = RoleType.unknown) -> GameSnapshot:
    # Determine if night action is required for this player
    night_action_required = False
    if game.game_status == GameStatus.night:
        current_player = next((p for p in game.players if p.id == player_id), None)
        if current_player and current_player.is_alive and not current_player.night_action_done:
            night_action_required = True

    return GameSnapshot(
        game_id=game.game_id,
        player_id=player_id,
        game_status=game.game_status,
        current_round=game.current_round,
        current_speaker_id=game.current_speaker_id,
        started=game.started,
        winner_faction=game.winner_faction,
        players=game.players,
        my_role=my_role,
        night_action_required=night_action_required,
        room_settings=_room_settings_view(game.room_settings),
    )


def _alive_speak_order(game: GameState) -> list[str]:
    return [player.id for player in game.players if player.is_alive]


def begin_speak_turn(game_id: str) -> str | None:
    game = _get_game_or_raise(game_id)
    game.speak_order = _alive_speak_order(game)
    game.current_speaker_id = game.speak_order[0] if game.speak_order else None
    game.speak_turn_submitted = False
    return game.current_speaker_id


def advance_speak_turn(game_id: str) -> str | None:
    game = _get_game_or_raise(game_id)
    if not game.speak_order:
        game.current_speaker_id = None
        game.speak_turn_submitted = False
        return None

    if game.current_speaker_id in game.speak_order:
        next_index = game.speak_order.index(game.current_speaker_id) + 1
    else:
        next_index = 0

    if next_index >= len(game.speak_order):
        game.current_speaker_id = None
        game.speak_turn_submitted = False
        return None

    game.current_speaker_id = game.speak_order[next_index]
    game.speak_turn_submitted = False
    return game.current_speaker_id


def _assign_roles(players: Iterable[Player], preset: str = "six-player-dark") -> None:
    player_list = list(players)
    total = len(player_list)
    if preset == "six-player-dark" and total == 6:
        roles = [
            RoleType.wolf,
            RoleType.wolf,
            RoleType.prophet,
            RoleType.guard,
            RoleType.civilian,
            RoleType.civilian,
        ]
    else:
        n_wolves = max(1, total // 4)
        n_prophets = 1 if total >= 4 else 0
        n_guards = 1 if total >= 6 else 0
        roles = []
        roles.extend([RoleType.wolf] * n_wolves)
        roles.extend([RoleType.prophet] * n_prophets)
        roles.extend([RoleType.guard] * n_guards)
        roles.extend([RoleType.civilian] * (total - n_wolves - n_prophets - n_guards))

    random.shuffle(roles)

    for index, player in enumerate(player_list):
        player.role = roles[index]


def create_game(player_name: str) -> GameSnapshot:
    game_id = generate_game_id()
    owner_player_id = generate_player_id()
    players = [Player(id=owner_player_id, name=player_name, role=RoleType.unknown)]
    _GAMES[game_id] = GameState(game_id=game_id, players=players, owner_player_id=owner_player_id)
    return _snapshot(_GAMES[game_id], owner_player_id)


def join_game(game_id: str, player_name: str) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    if game.started:
        raise AppError("游戏已开始，无法加入", status_code=409)
    if len(game.players) >= game.room_settings.scene.player_count:
        raise AppError("房间已满", status_code=409)

    player_id = generate_player_id()
    game.players.append(Player(id=player_id, name=player_name, role=RoleType.unknown))
    game.announcements.append(f"{player_name} 加入房间")
    return _snapshot(game, player_id)


def get_game(game_id: str, requester_id: str | None = None) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    pid = requester_id if requester_id else game.owner_player_id
    my_role = RoleType.unknown
    if pid:
        player = next((p for p in game.players if p.id == pid), None)
        if player and game.started:
            my_role = player.role
    return _snapshot(game, pid, my_role)


def update_room_settings(game_id: str, payload: RoomSettingsUpdate) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    if game.started:
        raise AppError("游戏已开始，无法修改设置", status_code=409)

    game.room_settings.scene = payload.scene
    game.room_settings.ai.base_url = payload.ai.base_url
    if payload.ai.api_key.strip():
        game.room_settings.ai.api_key = payload.ai.api_key
    game.room_settings.ai.model = payload.ai.model
    game.room_settings.ai.timeout_seconds = payload.ai.timeout_seconds
    game.room_settings.ai.temperature = payload.ai.temperature
    game.room_settings.ai.enable_mock = payload.ai.enable_mock
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
        return _snapshot(game, game.owner_player_id, game.players[0].role if game.players else RoleType.unknown)
    target_players = game.room_settings.scene.player_count
    if len(game.players) > target_players:
        raise AppError("房间人数超过场景上限", status_code=409)
    if len(game.players) < 1:
        raise AppError("人数不足，无法开局", status_code=409)

    if len(game.players) < target_players:
        game.players.extend(_build_ai_players(target_players - len(game.players)))

    _assign_roles(game.players, game.room_settings.scene.preset)
    game.started = True
    game.game_status = GameStatus.night
    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False
    game.announcements.append("游戏开始")
    return _snapshot(game, game.owner_player_id, RoleType.unknown)


def get_player_role(game_id: str, player_id: str) -> RoleType:
    game = _get_game_or_raise(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    return player.role


def record_speak(game_id: str, player_id: str, content: str) -> None:
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.speak:
        raise AppError("当前阶段不能发言", status_code=409)
    speaker = next((item for item in game.players if item.id == player_id), None)
    if speaker is None:
        raise AppError("玩家不存在", status_code=404)
    if not speaker.is_alive:
        raise AppError("玩家已死亡，无法发言", status_code=409)
    if game.current_speaker_id is None:
        raise AppError("当前没有发言轮次", status_code=409)
    if game.current_speaker_id != speaker.id:
        raise AppError("当前不是你的发言轮次", status_code=409)
    if game.speak_turn_submitted:
        raise AppError("本轮发言已提交", status_code=409)
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
    game.speak_turn_submitted = True
    game.announcements.append("收到一条发言")


def record_vote(game_id: str, voter_id: str, target_id: str) -> None:
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.vote:
        raise AppError("当前阶段不能投票", status_code=409)
    if voter_id == target_id:
        raise AppError("不能投票给自己", status_code=409)
    voter = next((item for item in game.players if item.id == voter_id), None)
    if voter is None:
        raise AppError("玩家不存在", status_code=404)
    game.votes = [vote for vote in game.votes if vote.get("voterId") != voter.id]
    game.votes.append({"voterId": voter.id, "targetId": target_id})
    game.announcements.append("收到一票")


def record_night_action(game_id: str, player_id: str, target_id: str) -> None:
    """Record a night action (wolf kill or prophet check) for a player."""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.night:
        raise AppError("当前不是夜间阶段", status_code=409)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    if not player.is_alive:
        raise AppError("玩家已死亡，无法行动", status_code=409)
    if player.role not in {RoleType.wolf, RoleType.prophet, RoleType.guard}:
        raise AppError("当前身份不能执行夜间行动", status_code=409)

    target = next((item for item in game.players if item.id == target_id), None)
    if target is None or not target.is_alive:
        raise AppError("目标不存在或已死亡", status_code=404)

    if target_id == player_id:
        raise AppError("不能对自己执行夜间行动", status_code=409)

    if player.role == RoleType.guard and player.last_guard_target_id == target_id:
        raise AppError("守卫不能连续两晚守护同一人", status_code=409)

    game.night_actions = [action for action in game.night_actions if action.get("playerId") != player_id]
    game.night_actions.append({"playerId": player_id, "targetId": target_id, "role": player.role.value})
    player.night_action_done = True


def get_night_targets(game_id: str, player_id: str) -> list[Player]:
    """Return alive targets for night action."""
    game = _get_game_or_raise(game_id)
    return [p for p in game.players if p.is_alive and p.id != player_id]


def resolve_night(game_id: str) -> dict[str, object]:
    """Resolve night phase: tally wolf kills, process prophet checks,
    mark killed players, reset night_action_done, clear night_actions.
    Returns {killed_player_id: str | None, checked_results: list}.
    """
    game = _get_game_or_raise(game_id)

    # --- Wolf kill: majority vote among wolves ---
    wolf_targets: list[str] = []
    guard_targets: list[str] = []
    for action in game.night_actions:
        if action.get("role") == RoleType.wolf.value:
            wolf_targets.append(str(action.get("targetId", "")))
        if action.get("role") == RoleType.guard.value:
            guard_targets.append(str(action.get("targetId", "")))

    killed_player_id: str | None = None
    if wolf_targets:
        tally: dict[str, int] = {}
        for tid in wolf_targets:
            tally[tid] = tally.get(tid, 0) + 1
        killed_player_id = max(tally, key=tally.get)  # type: ignore[arg-type]

    guarded_player_id = guard_targets[-1] if guard_targets else None
    blocked_by_guard = bool(killed_player_id and guarded_player_id and killed_player_id == guarded_player_id)
    if blocked_by_guard:
        killed_player_id = None

    # --- Prophet check: return check results ---
    checked_results: list[dict[str, object]] = []
    for action in game.night_actions:
        if action.get("role") == RoleType.prophet.value:
            target_id = str(action.get("targetId", ""))
            target = next((p for p in game.players if p.id == target_id), None)
            if target:
                is_wolf = target.role == RoleType.wolf
                checked_results.append({
                    "playerId": action.get("playerId"),
                    "targetId": target_id,
                    "isWolf": is_wolf,
                })

    # --- Mark killed player as dead ---
    if killed_player_id:
        killed_player = next((p for p in game.players if p.id == killed_player_id), None)
        if killed_player:
            killed_player.is_alive = False
            game.announcements.append(f"{killed_player.name} 在夜晚被杀害")
    elif blocked_by_guard:
        game.announcements.append("守卫成功守住了狼人袭击")
    elif guard_targets:
        game.announcements.append("守卫完成守护")

    for action in game.night_actions:
        if action.get("role") == RoleType.guard.value:
            guarded_target_id = str(action.get("targetId", ""))
            guard_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
            if guard_player:
                guard_player.last_guard_target_id = guarded_target_id

    # --- Reset night_action_done for all players ---
    for player in game.players:
        player.night_action_done = False

    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False

    # --- Clear night_actions ---
    game.night_actions.clear()

    # --- Check win condition ---
    alive_wolves = sum(1 for p in game.players if p.is_alive and p.role == RoleType.wolf)
    alive_others = sum(1 for p in game.players if p.is_alive and p.role != RoleType.wolf)

    if alive_wolves == 0:
        game.winner_faction = "civilian"
        game.game_status = GameStatus.end
    elif alive_wolves >= alive_others:
        game.winner_faction = "wolf"
        game.game_status = GameStatus.end

    return {
        "killed_player_id": killed_player_id,
        "guarded_player_id": guarded_player_id,
        "guard_blocked": blocked_by_guard,
        "checked_results": checked_results,
    }


def resolve_vote_round(game_id: str) -> dict[str, object]:
    game = _get_game_or_raise(game_id)
    if not game.votes:
        game.current_speaker_id = None
        game.speak_order.clear()
        game.speak_turn_submitted = False
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
    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False

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
