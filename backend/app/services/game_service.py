from dataclasses import dataclass, field
import random
from typing import Dict, Iterable

from app.core.exceptions import AppError
from app.domain.enums import GameStatus, RoleType
from app.domain.roles import (
    SKILL_REGISTRY,
    get_preset,
    build_role_list,
    get_night_action_roles,
)
from app.schemas.game import AiConfigView, GameResult, GameSnapshot, RoomSettings, RoomSettingsUpdate, SceneConfig
from app.schemas.player import Player
from app.utils.time import utc_now_iso
from app.utils.ids import generate_game_id, generate_player_id


def _check_win_condition(game: "GameState", win_condition: str = "slaughter_edge") -> str | None:
    """检查胜负条件，返回胜利阵营或 None。
    使用角色技能注册表判断阵营，支持动态角色组合。
    win_condition 规则：
      - slaughter_edge: 狼人全灭→好人胜；平民全灭→狼人胜（屠民）；神职全灭→狼人胜（屠神）
    """
    alive_wolves = [p for p in game.players if p.is_alive and SKILL_REGISTRY[p.role].faction == "wolf"]
    alive_civilians = [p for p in game.players if p.is_alive and p.role == RoleType.civilian]
    alive_gods = [
        p for p in game.players
        if p.is_alive
        and SKILL_REGISTRY[p.role].faction == "civilian"
        and p.role != RoleType.civilian
    ]

    if not alive_wolves:
        return "civilian"

    if win_condition == "slaughter_edge":
        if not alive_civilians:
            return "wolf"  # 屠民
        if not alive_gods:
            return "wolf"  # 屠神
    # 未来可扩展其他 win_condition

    return None


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
    from app.services.config_service import apply_saved_config_to_defaults

    # 优先使用持久化配置，其次使用环境变量
    saved = apply_saved_config_to_defaults()

    return AiRuntimeConfig(
        base_url=saved.get("base_url") or settings.ai_api_base_url,
        api_key=saved.get("api_key") or settings.ai_api_key,
        model=saved.get("model") or settings.ai_model,
        timeout_seconds=saved.get("timeout_seconds") or settings.ai_timeout_seconds,
        temperature=saved.get("temperature") or settings.ai_temperature,
        enable_mock=saved.get("enable_mock") if saved.get("enable_mock") is not None else settings.ai_enable_mock,
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
    deadline: str | None = None  # ISO 8601 UTC 时间戳，null 表示无活跃计时器
    # 抢身份相关
    role_selections: dict[str, str] = field(default_factory=dict)  # {player_id: chosen_role}
    game_mode: str = "classic"  # 游戏模式：classic / role_select
    # 每轮事件记录（用于贡献率计算）
    round_events: list[dict[str, object]] = field(default_factory=list)
    # 警长相关
    sheriff_id: str | None = None  # 当前警长玩家 ID
    sheriff_candidate_ids: list[str] = field(default_factory=list)  # 竞选候选人列表
    sheriff_withdrew_ids: list[str] = field(default_factory=list)  # 竞选中退水的玩家（本阶段失去投票权）
    sheriff_votes: list[dict[str, object]] = field(default_factory=list)  # 警长竞选投票
    sheriff_campaign_submitted: bool = False  # 竞选发言已提交标记
    # 狼人自爆相关
    wolf_self_destructed: str | None = None  # 自爆狼人玩家 ID（None 表示无自爆）
    sheriff_self_destruct_count: int = 0  # 竞选阶段狼人自爆次数（双爆吞警徽）
    # 猎人开枪相关
    pending_hunter_shoot: str | None = None  # 待开枪的猎人玩家 ID
    hunter_killed_by_poison: bool = False  # 猎人是否被毒杀（毒杀不能开枪）
    # 发言方向相关
    speak_direction: str | None = None  # 发言方向（left/right），由警长选择
    first_dead_player_id: str | None = None  # 昨夜死亡玩家ID（用于确定发言起点）
    # 房间码
    room_code: str = ""  # 6位房间码，用于联机


_GAMES: Dict[str, GameState] = {}
_ROOM_CODE_MAP: Dict[str, str] = {}  # room_code → game_id


def _generate_room_code() -> str:
    """生成6位数字房间码，确保唯一"""
    import random as _random
    for _ in range(100):
        code = ''.join(str(_random.randint(0, 9)) for _ in range(6))
        if code not in _ROOM_CODE_MAP:
            return code
    # 极端情况：生成8位
    return ''.join(str(_random.randint(0, 9)) for _ in range(8))


def _build_ai_players(count: int) -> list[Player]:
    return [
        Player(id=generate_player_id(), name=f"AI-{index + 1}", role=RoleType.unknown, is_ai=True)
        for index in range(count)
    ]


def _assign_seat_numbers(players: list[Player]) -> None:
    """分配座位号：已选座的玩家保留座位，只给 seat_number==0 的玩家（AI）分配。"""
    occupied = {p.seat_number for p in players if p.seat_number > 0}
    next_available = 1
    for p in players:
        if p.seat_number == 0:
            while next_available in occupied:
                next_available += 1
            p.seat_number = next_available
            occupied.add(next_available)
            next_available += 1


def seat_label(player: Player) -> str:
    """返回玩家显示标签：'{N}号({name})'"""
    return f"{player.seat_number}号({player.name})"


def _validate_seats(game: "GameState", max_seats: int) -> None:
    """验证座位号：唯一性、边界（1~max_seats）、无缺失"""
    seats = [p.seat_number for p in game.players]
    # 检查边界
    for s in seats:
        if s < 1 or s > max_seats:
            raise AppError(f"座位号 {s} 超出范围 1~{max_seats}", status_code=409)
    # 检查唯一性
    if len(seats) != len(set(seats)):
        raise AppError("存在重复座位号，请重新分配", status_code=409)


def get_seat_map(game_id: str) -> dict[str, int]:
    """返回 {player_id: seat_number} 映射"""
    game = _get_game_or_raise(game_id)
    return {p.id: p.seat_number for p in game.players}


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
        if current_player and current_player.is_alive and not current_player.night_action_done and not current_player.is_spectator:
            night_action_required = True

    # 判断是否为观战者
    current_player = next((p for p in game.players if p.id == player_id), None)
    is_spectator = current_player.is_spectator if current_player else False

    # 隐藏其他玩家的角色信息：只有自己能看到自己的角色，观战者/游戏结束后看到所有
    safe_players = []
    for p in game.players:
        if p.is_spectator:
            # 观战者自己不显示在玩家列表中
            continue
        if p.id == player_id or is_spectator or game.game_status == GameStatus.end:
            safe_players.append(p)
        else:
            safe_players.append(Player(
                id=p.id,
                name=p.name,
                seat_number=p.seat_number,
                role=RoleType.unknown,
                is_ai=p.is_ai,
                is_alive=p.is_alive,
                night_action_done=p.night_action_done,
                last_guard_target_id=p.last_guard_target_id,
                last_prophet_target_id=p.last_prophet_target_id,
                vote_immunity_used=p.vote_immunity_used,
                is_idiot_revealed=p.is_idiot_revealed,
                is_sheriff=p.is_sheriff,
                antidote_used=p.antidote_used,
                poison_used=p.poison_used,
                is_spectator=False,
            ))

    return GameSnapshot(
        game_id=game.game_id,
        player_id=player_id,
        game_status=game.game_status,
        current_round=game.current_round,
        current_speaker_id=game.current_speaker_id,
        started=game.started,
        winner_faction=game.winner_faction,
        players=safe_players,
        my_role=my_role,
        night_action_required=night_action_required,
        room_settings=_room_settings_view(game.room_settings),
        owner_player_id=game.owner_player_id,
        game_mode=game.game_mode,
        sheriff_id=game.sheriff_id,
        sheriff_candidate_ids=game.sheriff_candidate_ids,
        sheriff_withdrew_ids=game.sheriff_withdrew_ids,
        room_code=game.room_code,
        is_spectator=is_spectator,
    )


def _alive_speak_order(
    game: "GameState",
    speak_order_rule: str = "by_seat",
    sheriff_id: str | None = None,
    first_dead_player_id: str | None = None,
    speak_direction: str | None = None,
) -> list[str]:
    """根据规则生成发言顺序。
    - by_random: 随机
    - 有警长（sheriff_id 不为 None）：
      - 从警长旁边开始，按方向排列（默认"right"顺时针）
      - 警长放在最后发言
    - 无警长：
      - 单死（first_dead_player_id 有值）：从死者座位号下一位开始
      - 双死/平安夜：随机起始
    """
    alive = [p for p in game.players if p.is_alive]
    if speak_order_rule == "by_random":
        random.shuffle(alive)
        return [p.id for p in alive]

    # 按座位号排序
    alive.sort(key=lambda p: p.seat_number)

    if sheriff_id:
        # 有警长：从昨夜死者的下一位开始（如果有死者），按警长选择的方向排列，警长最后发言
        sheriff = next((p for p in alive if p.id == sheriff_id), None)
        if not sheriff:
            # 警长不在存活列表中（不应发生），回退到按座位
            return [p.id for p in alive]

        direction = speak_direction or "right"
        seat_count = len(alive)
        if seat_count <= 1:
            return [p.id for p in alive]

        # 排除警长，得到其他存活玩家
        others = [p for p in alive if p.id != sheriff_id]
        if not others:
            return [p.id for p in alive]

        # 确定起始位置
        start_index = 0
        if first_dead_player_id:
            # 有死者：从死者座位号的下一位开始
            dead_player = next((p for p in game.players if p.id == first_dead_player_id), None)
            if dead_player:
                dead_seat = dead_player.seat_number
                # 在排除警长的列表中，找第一个座位号 > dead_seat 的玩家
                for i, p in enumerate(others):
                    if p.seat_number > dead_seat:
                        start_index = i
                        break
                else:
                    # 死者座位号最大，从第一个玩家开始
                    start_index = 0
        else:
            # 无死者（平安夜或双死）：随机起始位置
            start_index = random.randint(0, len(others) - 1) if others else 0

        # 按方向排列
        ordered_others = []
        if direction == "left":
            # 逆时针：从起始位置逆向排列
            for i in range(len(others)):
                ordered_others.append(others[(start_index - i) % len(others)])
        else:
            # 顺时针：从起始位置顺向排列
            for i in range(len(others)):
                ordered_others.append(others[(start_index + i) % len(others)])

        # 警长放最后
        result = [p.id for p in ordered_others] + [sheriff_id]
        return result

    # 无警长
    if first_dead_player_id:
        # 单死：从死者座位号下一位开始
        dead_player = next((p for p in game.players if p.id == first_dead_player_id), None)
        if dead_player:
            # 找到死者座位号之后第一个存活玩家
            dead_seat = dead_player.seat_number
            # 按座位号排序的存活列表中，找第一个座位号 > dead_seat 的玩家
            start_index = 0
            for i, p in enumerate(alive):
                if p.seat_number > dead_seat:
                    start_index = i
                    break
            else:
                start_index = 0  # 死者座位号最大，从第一个存活玩家开始

            # 从 start_index 开始绕一圈
            result_ids = []
            for i in range(len(alive)):
                result_ids.append(alive[(start_index + i) % len(alive)].id)
            return result_ids

    # 双死/平安夜：随机起始
    if alive:
        start = random.randint(0, len(alive) - 1)
        result_ids = []
        for i in range(len(alive)):
            result_ids.append(alive[(start + i) % len(alive)].id)
        return result_ids

    return [p.id for p in alive]


def begin_speak_turn(
    game_id: str,
    speak_order_rule: str = "by_seat",
    sheriff_id: str | None = None,
    first_dead_player_id: str | None = None,
    speak_direction: str | None = None,
) -> str | None:
    game = _get_game_or_raise(game_id)
    game.speak_order = _alive_speak_order(
        game, speak_order_rule,
        sheriff_id=sheriff_id,
        first_dead_player_id=first_dead_player_id,
        speak_direction=speak_direction,
    )
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
    """根据场景预设分配角色。使用角色技能注册表的 build_role_list。
    确保角色数量与玩家数精确匹配。"""
    player_list = list(players)
    total = len(player_list)

    # 使用注册表构建角色列表
    try:
        roles = build_role_list(preset)
    except ValueError:
        # 未知预设时使用动态公式（包含主流神职）
        n_wolves = max(1, total // 3)  # 约 1/3 是狼人
        remaining = total - n_wolves
        # 至少分配预言家
        roles: list[RoleType] = [RoleType.wolf] * n_wolves
        if remaining >= 1:
            roles.append(RoleType.prophet)
            remaining -= 1
        if remaining >= 1 and total >= 6:
            roles.append(RoleType.guard)
            remaining -= 1
        if remaining >= 1 and total >= 9:
            roles.append(RoleType.hunter)
            remaining -= 1
        if remaining >= 1 and total >= 12:
            roles.append(RoleType.witch)
            remaining -= 1
        if remaining >= 1 and total >= 12:
            roles.append(RoleType.idiot)
            remaining -= 1
        # 剩余的填平民
        roles.extend([RoleType.civilian] * max(0, remaining))
        random.shuffle(roles)

    # 确保角色数与玩家数精确匹配
    if len(roles) != total:
        if len(roles) > total:
            # 多余则截断，优先保留狼人
            wolves = [r for r in roles if r == RoleType.wolf]
            others = [r for r in roles if r != RoleType.wolf]
            random.shuffle(others)
            roles = wolves[:total] if len(wolves) >= total else wolves + others[:total - len(wolves)]
        else:
            roles.extend([RoleType.civilian] * (total - len(roles)))
        random.shuffle(roles)

    for index, player in enumerate(player_list):
        player.role = roles[index]


def create_game(player_name: str) -> GameSnapshot:
    game_id = generate_game_id()
    owner_player_id = generate_player_id()
    players = [Player(id=owner_player_id, name=player_name, seat_number=1, role=RoleType.unknown)]
    room_code = _generate_room_code()
    _GAMES[game_id] = GameState(
        game_id=game_id, players=players, owner_player_id=owner_player_id, room_code=room_code,
    )
    _ROOM_CODE_MAP[room_code] = game_id
    return _snapshot(_GAMES[game_id], owner_player_id)


def join_game(game_id: str, player_name: str, preferred_seat: int | None = None) -> GameSnapshot:
    game = _get_game_or_raise(game_id)
    if game.started:
        raise AppError("游戏已开始，无法加入", status_code=409)

    max_seats = game.room_settings.scene.player_count
    if len(game.players) >= max_seats:
        raise AppError("房间已满", status_code=409)

    # 验证/分配座位
    occupied = {p.seat_number for p in game.players if p.seat_number > 0}
    if preferred_seat is not None:
        if preferred_seat < 1 or preferred_seat > max_seats:
            raise AppError(f"座位号必须在 1~{max_seats} 之间", status_code=400)
        if preferred_seat in occupied:
            raise AppError(f"{preferred_seat}号座位已被占用", status_code=409)
    else:
        # 自动分配：第一个空座
        preferred_seat = next((s for s in range(1, max_seats + 1) if s not in occupied), None)
        if preferred_seat is None:
            raise AppError("没有可用座位", status_code=409)

    player_id = generate_player_id()
    game.players.append(Player(
        id=player_id, name=player_name, seat_number=preferred_seat, role=RoleType.unknown,
    ))
    game.announcements.append(f"{player_name} 加入房间，坐在 {preferred_seat}号")
    return _snapshot(game, player_id)


def change_seat(game_id: str, player_id: str, seat_number: int) -> GameSnapshot:
    """在房间内换座位"""
    game = _get_game_or_raise(game_id)
    if game.started:
        raise AppError("游戏已开始，无法换座", status_code=409)

    max_seats = game.room_settings.scene.player_count
    if seat_number < 1 or seat_number > max_seats:
        raise AppError(f"座位号必须在 1~{max_seats} 之间", status_code=400)

    player = next((p for p in game.players if p.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)

    occupied = {p.seat_number for p in game.players if p.seat_number > 0 and p.id != player_id}
    if seat_number in occupied:
        raise AppError(f"{seat_number}号座位已被占用", status_code=409)

    player.seat_number = seat_number
    return _snapshot(game, player_id)


def find_game_by_room_code(room_code: str) -> str | None:
    """通过房间码查找游戏ID"""
    return _ROOM_CODE_MAP.get(room_code.strip())


def join_as_spectator(game_id: str, player_name: str) -> GameSnapshot:
    """以观战者身份加入游戏（游戏已开始后也可加入）"""
    game = _get_game_or_raise(game_id)
    if not game.started:
        raise AppError("游戏尚未开始，请以玩家身份加入", status_code=409)

    player_id = generate_player_id()
    spectator = Player(
        id=player_id,
        name=player_name,
        seat_number=0,  # 观战者无座位
        role=RoleType.unknown,
        is_ai=False,
        is_alive=False,
        is_spectator=True,
    )
    game.players.append(spectator)
    game.announcements.append(f"{player_name} 进入观战")
    # 观战者看到所有角色
    return _snapshot(game, player_id, RoleType.unknown)
def set_deadline(game_id: str, timeout_seconds: float) -> str:
    """为当前计时阶段设置截止时间。返回 ISO 8601 UTC 时间戳。"""
    from datetime import datetime, timezone, timedelta
    game = _get_game_or_raise(game_id)
    deadline_dt = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
    deadline_iso = deadline_dt.isoformat()
    game.deadline = deadline_iso
    return deadline_iso


def clear_deadline(game_id: str) -> None:
    """清除截止时间"""
    game = _get_game_or_raise(game_id)
    game.deadline = None


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
    game.room_settings.ai.base_url = payload.ai.base_url.strip()
    if payload.ai.api_key.strip():
        game.room_settings.ai.api_key = payload.ai.api_key.strip()
    game.room_settings.ai.model = payload.ai.model.strip()
    game.room_settings.ai.timeout_seconds = payload.ai.timeout_seconds
    game.room_settings.ai.temperature = payload.ai.temperature
    game.room_settings.ai.enable_mock = payload.ai.enable_mock

    # 自动关闭 mock 模式：当有有效的 base_url 和 api_key 时
    if game.room_settings.ai.base_url and game.room_settings.ai.api_key and game.room_settings.ai.enable_mock:
        game.room_settings.ai.enable_mock = False

    # 持久化 AI 配置到文件
    from app.services.config_service import save_config
    save_config(game.room_settings.ai)

    return _snapshot(game, game.owner_player_id)


def get_game_state(game_id: str) -> GameState:
    return _get_game_or_raise(game_id)


# ─── 状态机校验 ──────────────────────────────────────────────────────────────

# 允许的状态转换映射：{from_status: [to_status]}
VALID_TRANSITIONS: dict[GameStatus, set[GameStatus]] = {
    GameStatus.waiting: {GameStatus.role_select, GameStatus.night, GameStatus.end},
    GameStatus.role_select: {GameStatus.night, GameStatus.end},
    GameStatus.night: {GameStatus.day, GameStatus.night, GameStatus.end},
    GameStatus.day: {GameStatus.sheriff_election, GameStatus.speak, GameStatus.end},
    GameStatus.sheriff_election: {GameStatus.speak, GameStatus.day, GameStatus.night, GameStatus.end},
    GameStatus.speak: {GameStatus.vote, GameStatus.night, GameStatus.end},
    GameStatus.vote: {GameStatus.night, GameStatus.end},
    GameStatus.end: set(),  # 终态不可转换
}

# 各状态允许的操作
VALID_ACTIONS: dict[GameStatus, set[str]] = {
    GameStatus.waiting: {"speak", "change_seat", "start", "join"},
    GameStatus.role_select: {"role_select_choice"},
    GameStatus.night: {"night_action", "last_words", "wolf_self_destruct"},
    GameStatus.day: {"last_words", "wolf_self_destruct"},
    GameStatus.sheriff_election: {"sheriff_campaign", "sheriff_vote", "speak", "last_words", "wolf_self_destruct"},
    GameStatus.speak: {"speak", "last_words", "wolf_self_destruct"},
    GameStatus.vote: {"vote", "wolf_self_destruct"},
    GameStatus.end: set(),
}


def validate_state_transition(game_id: str, new_status: GameStatus) -> None:
    """校验状态转换是否合法。同状态设置视为无操作，直接通过。"""
    game = _get_game_or_raise(game_id)
    current = game.game_status
    if current == new_status:
        return  # 同状态无操作，合法
    allowed = VALID_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise AppError(
            f"非法状态转换: {current.value} → {new_status.value}",
            status_code=409,
        )


def validate_action(game_id: str, action: str) -> None:
    """校验当前状态是否允许该操作"""
    game = _get_game_or_raise(game_id)
    current = game.game_status
    allowed = VALID_ACTIONS.get(current, set())
    if action not in allowed:
        raise AppError(
            f"当前状态({current.value})不允许执行操作: {action}",
            status_code=409,
        )


# ────────────────────────────────────────────────────────────────────────────

def set_game_status(game_id: str, status: GameStatus) -> GameSnapshot:
    validate_state_transition(game_id, status)
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


def start_game(game_id: str, requester_id: str | None = None) -> GameSnapshot:
    game = _get_game_or_raise(game_id)

    # 房主校验
    if requester_id and requester_id != game.owner_player_id:
        raise AppError("只有房主可以开始游戏", status_code=403)

    if game.started:
        return _snapshot(game, game.owner_player_id, game.players[0].role if game.players else RoleType.unknown)
    target_players = game.room_settings.scene.player_count
    if len(game.players) > target_players:
        raise AppError("房间人数超过场景上限", status_code=409)
    if len(game.players) < 1:
        raise AppError("人数不足，无法开局", status_code=409)

    if len(game.players) < target_players:
        game.players.extend(_build_ai_players(target_players - len(game.players)))

    # 读取游戏模式
    game.game_mode = getattr(game.room_settings.scene, 'mode', 'classic') or 'classic'

    if game.game_mode == "role_select":
        # 抢身份模式：不立即分配角色，等抢身份阶段结束后分配
        game.started = True
        game.game_status = GameStatus.role_select
        game.current_speaker_id = None
        game.speak_order.clear()
        game.speak_turn_submitted = False
        game.announcements.append("游戏开始，进入抢身份阶段")
    else:
        # 经典模式：直接分配角色
        _assign_roles(game.players, game.room_settings.scene.preset)
        game.started = True
        game.game_status = GameStatus.night
        game.current_speaker_id = None
        game.speak_order.clear()
        game.speak_turn_submitted = False
        game.announcements.append("游戏开始")

    _assign_seat_numbers(game.players)
    # 验证座位号唯一性和边界
    _validate_seats(game, target_players)
    return _snapshot(game, game.owner_player_id, RoleType.unknown)


def get_player_role(game_id: str, player_id: str) -> RoleType:
    game = _get_game_or_raise(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    return player.role


def record_speak(game_id: str, player_id: str, content: str) -> None:
    game = _get_game_or_raise(game_id)
    if game.game_status not in (GameStatus.speak, GameStatus.day, GameStatus.sheriff_election):
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
            "playerName": f"{speaker.seat_number}号({speaker.name})",
            "content": content,
            "time": utc_now_iso(),
            "isAI": speaker.is_ai,
        }
    )
    # 警长竞选发言用 sheriff_campaign_submitted 标记
    if game.game_status == GameStatus.sheriff_election:
        game.sheriff_campaign_submitted = True
    else:
        game.speak_turn_submitted = True
    game.announcements.append("收到一条发言")


def record_sheriff_campaign_speak(game_id: str, player_id: str, content: str) -> None:
    """记录警长竞选发言。
    竞选发言不依赖普通发言轮次，只要求当前处于竞选阶段且候选人存活。"""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.sheriff_election:
        raise AppError("当前阶段不能进行竞选发言", status_code=409)

    speaker = next((item for item in game.players if item.id == player_id), None)
    if speaker is None:
        raise AppError("玩家不存在", status_code=404)
    if not speaker.is_alive:
        raise AppError("玩家已死亡，无法发言", status_code=409)

    game.chats.append(
        {
            "id": f"chat-{len(game.chats) + 1}",
            "playerId": speaker.id,
            "playerName": f"{speaker.seat_number}号({speaker.name})【竞选】",
            "content": content,
            "time": utc_now_iso(),
            "isAI": speaker.is_ai,
        }
    )
    game.sheriff_campaign_submitted = True
    game.announcements.append("收到一条竞选发言")


def record_last_words(game_id: str, player_id: str, content: str) -> None:
    """记录遗言。允许已死亡玩家在遗言阶段发言。
    遗言可能发生在夜间（首夜死亡）、投票后（被放逐）、发言阶段（狼人自爆）、竞选阶段（狼人自爆），
    此时 game_status 为 night、vote、speak 或 sheriff_election，
    通过 current_speaker_id 限制只有当前遗言者才能发言。"""
    game = _get_game_or_raise(game_id)
    if game.game_status not in (GameStatus.day, GameStatus.night, GameStatus.vote, GameStatus.speak, GameStatus.sheriff_election):
        raise AppError("当前不是遗言阶段", status_code=409)
    speaker = next((item for item in game.players if item.id == player_id), None)
    if speaker is None:
        raise AppError("玩家不存在", status_code=404)
    # 遗言阶段允许死亡玩家发言，但不能是存活的玩家乱发
    if speaker.is_alive:
        raise AppError("存活玩家不需要发表遗言", status_code=409)
    if game.current_speaker_id != speaker.id:
        raise AppError("当前不是你的遗言轮次", status_code=409)
    if game.speak_turn_submitted:
        raise AppError("遗言已提交", status_code=409)
    game.chats.append(
        {
            "id": f"chat-{len(game.chats) + 1}",
            "playerId": speaker.id,
            "playerName": f"{speaker.seat_number}号({speaker.name})【遗言】",
            "content": content,
            "time": utc_now_iso(),
            "isAI": speaker.is_ai,
        }
    )
    game.speak_turn_submitted = True
    game.announcements.append(f"{speaker.seat_number}号({speaker.name}) 发表了遗言")


def record_vote(game_id: str, voter_id: str, target_id: str) -> None:
    """记录投票。target_id 为空或 'abstain' 表示弃票。"""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.vote:
        raise AppError("当前阶段不能投票", status_code=409)
    # 弃票：target_id 为空或 'abstain' 时跳过自己检查
    is_abstain = not target_id or target_id == "abstain"
    if not is_abstain and voter_id == target_id:
        raise AppError("不能投票给自己", status_code=409)
    voter = next((item for item in game.players if item.id == voter_id), None)
    if voter is None:
        raise AppError("玩家不存在", status_code=404)
    # 白痴翻牌后不能投票
    if voter.vote_immunity_used:
        raise AppError("白痴翻牌后不能参与投票", status_code=409)
    game.votes = [vote for vote in game.votes if vote.get("voterId") != voter.id]
    if is_abstain:
        game.votes.append({"voterId": voter.id, "targetId": "abstain"})
    else:
        game.votes.append({"voterId": voter.id, "targetId": target_id})
    game.announcements.append("收到一票" if not is_abstain else "收到一票弃票")


def record_night_action(game_id: str, player_id: str, target_id: str, action_type: str = "", wolf_kill_target_id: str | None = None) -> None:
    """Record a night action for a player.
    action_type: optional, used for witch (\"save\"/\"poison\") to distinguish potion type.
    wolf_kill_target_id: the computed wolf kill target (used to validate witch save target).
    """
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.night:
        raise AppError("当前不是夜间阶段", status_code=409)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    if not player.is_alive:
        raise AppError("玩家已死亡，无法行动", status_code=409)
    if player.role not in {r for r, s in SKILL_REGISTRY.items() if s.has_night_action}:
        raise AppError("当前身份不能执行夜间行动", status_code=409)

    target = next((item for item in game.players if item.id == target_id), None)
    if target is None or not target.is_alive:
        raise AppError("目标不存在或已死亡", status_code=404)

    if target_id == player_id:
        skill = SKILL_REGISTRY[player.role]
        is_first_night = game.current_round == 1
        # 首夜允许自救（女巫首夜自救规则）
        if not skill.can_target_self and not (skill.can_target_self_first_night and is_first_night):
            raise AppError("不能对自己执行夜间行动", status_code=409)

    # 通用连续目标检查：根据角色类型获取对应的 last_target_id
    if not SKILL_REGISTRY[player.role].consecutive_target_allowed:
        last_target_id: str | None = None
        if player.role == RoleType.prophet:
            last_target_id = player.last_prophet_target_id
        elif player.role == RoleType.guard:
            last_target_id = player.last_guard_target_id
        if last_target_id and target_id == last_target_id:
            raise AppError(f"{SKILL_REGISTRY[player.role].name}不能连续两晚选择同一目标", status_code=409)

    # 女巫特殊校验：药剂各只能用一次；解药只能救刀口
    if player.role == RoleType.witch:
        if action_type == "save" and player.antidote_used:
            raise AppError("解药已经使用过", status_code=409)
        if action_type == "poison" and player.poison_used:
            raise AppError("毒药已经使用过", status_code=409)
        if action_type == "save":
            if wolf_kill_target_id and target_id != wolf_kill_target_id:
                raise AppError(f"解药只能解救被狼人袭击的玩家", status_code=409)
        if action_type not in ("save", "poison", ""):
            raise AppError("女巫必须选择使用解药(save)或毒药(poison)或跳过", status_code=400)

    game.night_actions = [action for action in game.night_actions if action.get("playerId") != player_id]
    game.night_actions.append({
        "playerId": player_id,
        "targetId": target_id,
        "role": player.role.value,
        "actionType": action_type,
    })
    player.night_action_done = True


def get_night_targets(game_id: str, player_id: str) -> list[Player]:
    """Return alive targets for night action. Includes self if can_target_self or can_target_self_first_night (首夜)."""
    game = _get_game_or_raise(game_id)
    player = next((p for p in game.players if p.id == player_id), None)
    if player:
        skill = SKILL_REGISTRY[player.role]
        is_first_night = game.current_round == 1
        can_include_self = skill.can_target_self or (skill.can_target_self_first_night and is_first_night)
        if can_include_self:
            return [p for p in game.players if p.is_alive]
    return [p for p in game.players if p.is_alive and p.id != player_id]


def resolve_night(game_id: str) -> dict[str, object]:
    """Resolve night phase: tally wolf kills, process prophet checks,
    mark killed players, reset night_action_done, clear night_actions.
    Returns {killed_player_id: str | None, checked_results: list}.
    """
    from app.domain.roles import get_preset_rule
    game = _get_game_or_raise(game_id)

    # --- Wolf kill: majority vote among wolves ---
    wolf_targets: list[str] = []
    guard_targets: list[str] = []
    witch_save_targets: list[str] = []
    witch_poison_targets: list[str] = []
    for action in game.night_actions:
        role_val = str(action.get("role", ""))
        target_id = str(action.get("targetId", ""))
        action_type = str(action.get("actionType", ""))
        if role_val == RoleType.wolf.value:
            wolf_targets.append(target_id)
        elif role_val == RoleType.guard.value:
            guard_targets.append(target_id)
        elif role_val == RoleType.witch.value:
            if action_type == "save":
                witch_save_targets.append(target_id)
            elif action_type == "poison":
                witch_poison_targets.append(target_id)

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

    # --- Witch antidote: save the killed player ---
    # 奶穿规则：如果守卫和女巫同时保护同一目标，该目标死亡（守护+解药互相抵消）
    witch_saved = False
    witch_saved_player_id: str | None = None
    double_protected_death = False
    if killed_player_id and witch_save_targets:
        for save_target in witch_save_targets:
            if save_target == killed_player_id:
                # 标记女巫解药已使用（无论是否成功都要消耗解药）
                for action in game.night_actions:
                    if str(action.get("role", "")) == RoleType.witch.value and str(action.get("actionType", "")) == "save":
                        witch_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
                        if witch_player:
                            witch_player.antidote_used = True
                # 奶穿检查：守卫守了同一个人 → 死亡
                if guarded_player_id and killed_player_id == guarded_player_id:
                    double_protected_death = True
                    witch_saved = False
                    game.announcements.append("守卫和女巫同时保护同一目标，发生奶穿")
                else:
                    witch_saved = True
                    witch_saved_player_id = killed_player_id
                    killed_player_id = None
                break

    # --- Witch poison: kill the poisoned target (毒药不受守卫保护) ---
    witch_poisoned_player_id: str | None = None
    if witch_poison_targets:
        poison_target = witch_poison_targets[0]  # 取第一个毒杀目标
        poison_target_player = next((p for p in game.players if p.id == poison_target), None)
        if poison_target_player and poison_target_player.is_alive:
            # 不能毒杀已被狼人杀死的人（如果被守卫守住或被女巫救活则可以被毒）
            if poison_target != killed_player_id or killed_player_id is None:
                witch_poisoned_player_id = poison_target
            # 标记女巫毒药已使用
            for action in game.night_actions:
                if str(action.get("role", "")) == RoleType.witch.value and str(action.get("actionType", "")) == "poison":
                    witch_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
                    if witch_player:
                        witch_player.poison_used = True

    # 合并死亡：狼杀 + 毒杀（两者可能不同）
    all_killed_ids = set()
    if killed_player_id:
        all_killed_ids.add(killed_player_id)
    if witch_poisoned_player_id:
        all_killed_ids.add(witch_poisoned_player_id)

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

    # --- Mark killed players as dead (狼杀 + 毒杀) ---
    for dead_id in all_killed_ids:
        dead_player = next((p for p in game.players if p.id == dead_id), None)
        if dead_player:
            dead_player.is_alive = False
            # 记录狼人击杀
            if dead_id == killed_player_id:
                wolf_killers = []
                for action in game.night_actions:
                    if str(action.get("role", "")) == RoleType.wolf.value and str(action.get("targetId", "")) == dead_id:
                        killer = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
                        if killer:
                            wolf_killers.append(f"{killer.seat_number}号({killer.name})")
                killer_info = "、".join(wolf_killers) if wolf_killers else "狼人"
                game.announcements.append(f"{killer_info} 夜间击杀了 {dead_player.seat_number}号({dead_player.name})")
            # 记录女巫毒杀
            if dead_id == witch_poisoned_player_id:
                witch_player = None
                for action in game.night_actions:
                    if str(action.get("role", "")) == RoleType.witch.value and str(action.get("actionType", "")) == "poison":
                        witch_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
                        break
                witch_label = f"{witch_player.seat_number}号({witch_player.name})" if witch_player else "女巫"
                game.announcements.append(f"{witch_label} 使用毒药毒杀了 {dead_player.seat_number}号({dead_player.name})")

    if witch_saved:
        saved_player = next((p for p in game.players if p.id == witch_saved_player_id), None)
        saved_name = f"{saved_player.seat_number}号({saved_player.name})" if saved_player else "某玩家"
        game.announcements.append(f"女巫使用解药救活了 {saved_name}")
    elif blocked_by_guard:
        game.announcements.append("守卫成功守住了狼人袭击")
    elif guard_targets and not killed_player_id:
        game.announcements.append("守卫完成守护")

    # --- 记录夜间事件（贡献率用） ---
    round_event: dict[str, object] = {
        "type": "night",
        "round": game.current_round,
        "killed_player_id": killed_player_id,
        "guard_blocked": blocked_by_guard,
        "witch_saved": witch_saved,
        "witch_saved_player_id": witch_saved_player_id,
        "witch_poisoned_player_id": witch_poisoned_player_id,
        "all_killed_ids": list(all_killed_ids),
    }
    # 预言家查验
    prophet_checks = []
    for action in game.night_actions:
        if str(action.get("role", "")) == RoleType.prophet.value:
            target_id = str(action.get("targetId", ""))
            target = next((p for p in game.players if p.id == target_id), None)
            prophet_checks.append({
                "prophet_id": str(action.get("playerId", "")),
                "target_id": target_id,
                "is_wolf": target.role == RoleType.wolf if target else False,
            })
    round_event["prophet_checks"] = prophet_checks
    # 守卫守护
    guard_saves = []
    for action in game.night_actions:
        if str(action.get("role", "")) == RoleType.guard.value:
            guard_saves.append({
                "guard_id": str(action.get("playerId", "")),
                "target_id": str(action.get("targetId", "")),
                "saved": blocked_by_guard and str(action.get("targetId", "")) == killed_player_id,
            })
    round_event["guard_saves"] = guard_saves
    # 狼人击杀
    wolf_kills = []
    for action in game.night_actions:
        if str(action.get("role", "")) == RoleType.wolf.value:
            wolf_kills.append({
                "wolf_id": str(action.get("playerId", "")),
                "target_id": str(action.get("targetId", "")),
            })
    round_event["wolf_kills"] = wolf_kills
    game.round_events.append(round_event)

    for action in game.night_actions:
        if action.get("role") == RoleType.guard.value:
            guarded_target_id = str(action.get("targetId", ""))
            guard_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
            if guard_player:
                guard_player.last_guard_target_id = guarded_target_id

    # 记录预言家 last_prophet_target_id
    for action in game.night_actions:
        if action.get("role") == RoleType.prophet.value:
            prophet_target_id = str(action.get("targetId", ""))
            prophet_player = next((p for p in game.players if p.id == str(action.get("playerId", ""))), None)
            if prophet_player:
                prophet_player.last_prophet_target_id = prophet_target_id

    # 记录昨夜死亡玩家ID（用于发言顺序）
    if all_killed_ids:
        # 多死时随机选择一个死者作为发言起点参考
        killed_list = list(all_killed_ids)
        game.first_dead_player_id = random.choice(killed_list)
    else:
        game.first_dead_player_id = None

    # --- Reset night_action_done for all players ---
    for player in game.players:
        player.night_action_done = False

    # --- 猎人死亡检测：如果是猎人且非毒杀，触发开枪 ---
    game.pending_hunter_shoot = None
    game.hunter_killed_by_poison = False
    for dead_id in all_killed_ids:
        dead_player = next((p for p in game.players if p.id == dead_id), None)
        if dead_player and dead_player.role == RoleType.hunter:
            if dead_id == witch_poisoned_player_id:
                # 被毒杀的猎人不能开枪
                game.hunter_killed_by_poison = True
                game.announcements.append(f"猎人 {dead_player.seat_number}号({dead_player.name}) 被毒杀，无法开枪")
            else:
                # 被狼杀的猎人可以开枪
                game.pending_hunter_shoot = dead_id
                game.announcements.append(f"猎人 {dead_player.seat_number}号({dead_player.name}) 死亡，可以开枪")

    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False

    # --- Clear night_actions ---
    game.night_actions.clear()

    # --- Check win condition ---
    win_condition = get_preset_rule(game.room_settings.scene.preset, "win_condition")
    winner = _check_win_condition(game, win_condition)
    if winner:
        game.winner_faction = winner
        game.game_status = GameStatus.end

    return {
        "killed_player_id": killed_player_id,
        "guarded_player_id": guarded_player_id,
        "guard_blocked": blocked_by_guard,
        "checked_results": checked_results,
        "witch_saved": witch_saved,
        "witch_saved_player_id": witch_saved_player_id,
        "witch_poisoned_player_id": witch_poisoned_player_id,
        "all_killed_ids": list(all_killed_ids),
        "double_protected_death": double_protected_death,
    }


def resolve_vote_round(game_id: str, vote_tie_rule: str = "no_elimination") -> dict[str, object]:
    from app.domain.roles import get_preset_rule
    game = _get_game_or_raise(game_id)
    # 如果未显式传入 vote_tie_rule，从预设读取
    if vote_tie_rule == "no_elimination":
        vote_tie_rule = get_preset_rule(game.room_settings.scene.preset, "vote_tie_rule")

    if not game.votes:
        game.current_speaker_id = None
        game.speak_order.clear()
        game.speak_turn_submitted = False
        return {"eliminated": None, "winnerFaction": game.winner_faction}

    tally: dict[str, float] = {}
    for vote in game.votes:
        target_id = str(vote.get("targetId", ""))
        if target_id == "abstain":
            continue  # 弃票不计入
        voter_id = str(vote.get("voterId", ""))
        # 警长票权1.5倍
        weight = 1.5 if voter_id == game.sheriff_id else 1
        tally[target_id] = tally.get(target_id, 0) + weight

    # 检查平票：如果最高票不止一人，则无人出局
    if tally:
        max_votes = max(tally.values())
        top_candidates = [tid for tid, count in tally.items() if count == max_votes]
        if len(top_candidates) > 1:
            # 平票处理：根据 vote_tie_rule 决定
            if vote_tie_rule == "no_elimination":
                game.votes.clear()
                game.current_round += 1
                game.current_speaker_id = None
                game.speak_order.clear()
                game.speak_turn_submitted = False
                game.announcements.append("投票平票，无人出局")
                game.game_status = GameStatus.night
                return {"eliminated": None, "winnerFaction": game.winner_faction, "gameStatus": game.game_status, "currentRound": game.current_round}
            # 未来: re_vote / both_eliminated
            game.votes.clear()
            game.current_round += 1
            game.current_speaker_id = None
            game.speak_order.clear()
            game.speak_turn_submitted = False
            game.announcements.append("投票平票，无人出局")
            game.game_status = GameStatus.night
            return {"eliminated": None, "winnerFaction": game.winner_faction, "gameStatus": game.game_status, "currentRound": game.current_round}
        eliminated_id = top_candidates[0]
    else:
        eliminated_id = None

    eliminated_player = next((player for player in game.players if player.id == eliminated_id), None)
    idiot_immunity = False
    hunter_voted_out = False
    if eliminated_player is not None:
        # 白痴翻牌免疫：被投票放逐时不死亡，但之后不能投票
        if eliminated_player.role == RoleType.idiot and not eliminated_player.vote_immunity_used:
            eliminated_player.vote_immunity_used = True
            eliminated_player.is_idiot_revealed = True  # 白痴翻牌，公开可见
            idiot_immunity = True
            # 白痴免疫，不算淘汰，但仍记录谁被投
        else:
            eliminated_player.is_alive = False
            # 猎人被投票放逐，触发开枪
            if eliminated_player.role == RoleType.hunter:
                hunter_voted_out = True
                game.pending_hunter_shoot = eliminated_id
                game.hunter_killed_by_poison = False
        # 记录投票详情：谁投了谁，谁弃票了
        vote_detail_parts = []
        abstain_voters = []
        for vote in game.votes:
            voter = next((p for p in game.players if p.id == str(vote.get("voterId", ""))), None)
            target_id_str = str(vote.get("targetId", ""))
            if target_id_str == "abstain":
                if voter:
                    abstain_voters.append(f"{voter.seat_number}号({voter.name})")
            else:
                target = next((p for p in game.players if p.id == target_id_str), None)
                if voter and target:
                    vote_detail_parts.append(f"{voter.seat_number}号({voter.name})→{target.seat_number}号({target.name})")
        detail_msg = f"{eliminated_player.seat_number}号({eliminated_player.name}) 被投票淘汰"
        if vote_detail_parts:
            detail_msg += f"（{', '.join(vote_detail_parts)}）"
        if abstain_voters:
            detail_msg += f"；弃票：{', '.join(abstain_voters)}"
        game.announcements.append(detail_msg)

    # --- 记录投票事件（贡献率用），在 votes clear 前保存 ---
    vote_records = [dict(v) for v in game.votes]
    game.round_events.append({
        "type": "vote",
        "round": game.current_round,
        "votes": vote_records,
        "eliminated_id": eliminated_player.id if eliminated_player else None,
    })

    game.votes.clear()
    game.current_round += 1
    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False

    win_condition = get_preset_rule(game.room_settings.scene.preset, "win_condition")
    winner = _check_win_condition(game, win_condition)
    if winner:
        game.winner_faction = winner
        game.game_status = GameStatus.end
    else:
        # 投票后不进入发言，直接进入下一轮夜晚（由 AI 循环控制流程）
        game.game_status = GameStatus.night

    return {
        "eliminated": eliminated_player.id if eliminated_player and not idiot_immunity else None,
        "eliminated_id_for_detail": eliminated_player.id if eliminated_player else None,
        "idiot_immunity": idiot_immunity,
        "hunter_voted_out": hunter_voted_out,
        "winnerFaction": game.winner_faction,
        "gameStatus": game.game_status,
        "currentRound": game.current_round,
    }


def get_result(game_id: str) -> GameResult:
    game = _get_game_or_raise(game_id)

    # 计算贡献率
    from app.services.contribution_service import compute_contributions, get_mvp, get_svp
    contributions = compute_contributions(game.players, game.round_events, game.winner_faction)
    mvp = get_mvp(contributions, game.winner_faction)
    svp = get_svp(contributions, game.winner_faction)

    return GameResult(
        game_id=game.game_id,
        winner_faction=game.winner_faction or "pending",
        current_round=game.current_round,
        players=game.players,
        chats=game.chats,
        announcements=game.announcements,
        round_events=game.round_events,
        contributions=contributions,
        mvp=mvp,
        svp=svp,
    )


def record_role_selection(game_id: str, player_id: str, chosen_role: str) -> None:
    """记录玩家的抢身份选择"""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.role_select:
        raise AppError("当前不是抢身份阶段", status_code=409)
    player = next((p for p in game.players if p.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    if player.is_ai:
        raise AppError("AI玩家不能抢身份", status_code=409)
    # 校验角色是否在可用列表中
    try:
        RoleType(chosen_role)
    except ValueError:
        raise AppError(f"无效的角色类型: {chosen_role}", status_code=400)
    game.role_selections[player_id] = chosen_role


def get_role_selections(game_id: str) -> dict[str, str]:
    """获取所有玩家的抢身份选择"""
    game = _get_game_or_raise(game_id)
    return dict(game.role_selections)


def clear_role_selections(game_id: str) -> None:
    """清空抢身份选择"""
    game = _get_game_or_raise(game_id)
    game.role_selections.clear()


def assign_roles_from_selection(
    game_id: str,
    role_assignments: dict[str, RoleType],
) -> None:
    """根据抢身份结果分配角色"""
    game = _get_game_or_raise(game_id)
    for player_id, role in role_assignments.items():
        player = next((p for p in game.players if p.id == player_id), None)
        if player:
            player.role = role


# ------------------------------------------------------------------
#  警长竞选相关函数
# ------------------------------------------------------------------

def register_sheriff_campaign(game_id: str, player_id: str) -> None:
    """玩家上警（参加警长竞选）"""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.sheriff_election:
        raise AppError("当前不是警长竞选阶段", status_code=409)
    player = next((p for p in game.players if p.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    if not player.is_alive:
        raise AppError("已死亡玩家不能参加竞选", status_code=409)
    if player_id in game.sheriff_candidate_ids:
        raise AppError("你已经上警了", status_code=409)
    if player_id in game.sheriff_withdrew_ids:
        raise AppError("你已退水，本轮不能再上警", status_code=409)
    game.sheriff_candidate_ids.append(player_id)
    game.announcements.append(f"{player.seat_number}号({player.name}) 上警竞选")


def withdraw_sheriff_campaign(game_id: str, player_id: str) -> None:
    """玩家退选（退水）。
    网易规则：退水即放弃竞选 + 失去本阶段投票权。
    """
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.sheriff_election:
        raise AppError("当前不是警长竞选阶段", status_code=409)
    if player_id not in game.sheriff_candidate_ids:
        raise AppError("你未参加竞选", status_code=409)
    player = next((p for p in game.players if p.id == player_id), None)
    game.sheriff_candidate_ids.remove(player_id)
    if player_id not in game.sheriff_withdrew_ids:
        game.sheriff_withdrew_ids.append(player_id)
    if player:
        game.announcements.append(f"{player.seat_number}号({player.name}) 退选")


def record_sheriff_vote(game_id: str, voter_id: str, target_id: str) -> None:
    """记录警长竞选投票。target_id="abstain"表示弃权。"""
    game = _get_game_or_raise(game_id)
    if game.game_status != GameStatus.sheriff_election:
        raise AppError("当前不是警长竞选投票阶段", status_code=409)
    voter = next((p for p in game.players if p.id == voter_id), None)
    if voter is None:
        raise AppError("玩家不存在", status_code=404)
    if not voter.is_alive:
        raise AppError("已死亡玩家不能投票", status_code=409)
    if voter_id in game.sheriff_candidate_ids:
        raise AppError("候选人不能投票", status_code=409)
    if voter_id in game.sheriff_withdrew_ids:
        raise AppError("你已退水，本阶段不能投票", status_code=409)
    is_abstain = not target_id or target_id == "abstain"
    if not is_abstain:
        if target_id not in game.sheriff_candidate_ids:
            raise AppError("只能投给候选人", status_code=409)
    # 去重：同一人重新投则覆盖
    game.sheriff_votes = [v for v in game.sheriff_votes if v.get("voterId") != voter_id]
    if is_abstain:
        game.sheriff_votes.append({"voterId": voter_id, "targetId": "abstain"})
    else:
        game.sheriff_votes.append({"voterId": voter_id, "targetId": target_id})


def resolve_sheriff_election(game_id: str) -> dict[str, object]:
    """结算警长竞选。返回 {sheriff_id, is_tie}。"""
    game = _get_game_or_raise(game_id)

    # 如果没有候选人，无警长
    if not game.sheriff_candidate_ids:
        game.sheriff_votes.clear()
        return {"sheriff_id": None, "is_tie": False}

    # 如果只有一个候选人，直接当选
    if len(game.sheriff_candidate_ids) == 1:
        sheriff_id = game.sheriff_candidate_ids[0]
        _set_sheriff(game_id, sheriff_id)
        game.sheriff_votes.clear()
        return {"sheriff_id": sheriff_id, "is_tie": False}

    # 统计票数
    tally: dict[str, float] = {}
    for vote in game.sheriff_votes:
        tid = str(vote.get("targetId", ""))
        if tid == "abstain":
            continue
        tally[tid] = tally.get(tid, 0) + 1

    if not tally:
        # 全部弃权，无警长（无候选人能 PK）
        game.sheriff_votes.clear()
        return {"sheriff_id": None, "is_tie": True, "top_candidates": []}

    max_votes = max(tally.values())
    top_candidates = [tid for tid, count in tally.items() if count == max_votes]

    if len(top_candidates) > 1:
        # 平票，无人当选；返回 top_candidates 供 PK 发言阶段使用
        game.sheriff_votes.clear()
        return {"sheriff_id": None, "is_tie": True, "top_candidates": top_candidates}

    sheriff_id = top_candidates[0]
    _set_sheriff(game_id, sheriff_id)
    game.sheriff_votes.clear()
    return {"sheriff_id": sheriff_id, "is_tie": False, "top_candidates": top_candidates}


def _set_sheriff(game_id: str, sheriff_id: str) -> None:
    """设置警长"""
    game = _get_game_or_raise(game_id)
    # 清除旧警长标记
    for p in game.players:
        p.is_sheriff = False
    # 设置新警长
    player = next((p for p in game.players if p.id == sheriff_id), None)
    if player:
        player.is_sheriff = True
    game.sheriff_id = sheriff_id


def transfer_sheriff_badge(game_id: str, from_player_id: str, to_player_id: str) -> None:
    """警长转让徽章（警长死亡时选择继承人）"""
    game = _get_game_or_raise(game_id)
    if game.sheriff_id != from_player_id:
        raise AppError("你不是警长，不能转让徽章", status_code=409)
    target = next((p for p in game.players if p.id == to_player_id), None)
    if target is None:
        raise AppError("目标玩家不存在", status_code=404)
    if not target.is_alive:
        raise AppError("不能转让给已死亡的玩家", status_code=409)
    _set_sheriff(game_id, to_player_id)
    game.announcements.append(
        f"警长徽章由 {seat_label(next((p for p in game.players if p.id == from_player_id), target))} "
        f"转让给 {seat_label(target)}"
    )


def clear_sheriff_election(game_id: str) -> None:
    """清空竞选状态"""
    game = _get_game_or_raise(game_id)
    game.sheriff_candidate_ids.clear()
    game.sheriff_withdrew_ids.clear()
    game.sheriff_votes.clear()
    game.sheriff_campaign_submitted = False


# ------------------------------------------------------------------
#  狼人自爆相关函数
# ------------------------------------------------------------------

def wolf_self_destruct(game_id: str, player_id: str) -> dict[str, object]:
    """狼人自爆：狼人在白天发言/投票/竞选阶段选择自爆，立即死亡并跳过当天剩余流程。
    竞选阶段狼人自爆可影响警徽归属（双爆吞警徽）。
    返回 {player_id, player_name, winner_faction, in_sheriff_election}。"""
    game = _get_game_or_raise(game_id)
    if game.game_status not in (GameStatus.speak, GameStatus.vote, GameStatus.sheriff_election):
        raise AppError("当前阶段不能自爆（仅发言/投票/竞选阶段可用）", status_code=409)
    player = next((p for p in game.players if p.id == player_id), None)
    if player is None:
        raise AppError("玩家不存在", status_code=404)
    if not player.is_alive:
        raise AppError("已死亡玩家不能自爆", status_code=409)
    if SKILL_REGISTRY[player.role].faction != "wolf":
        raise AppError("只有狼人才能自爆", status_code=409)

    # 执行自爆
    player.is_alive = False
    game.wolf_self_destructed = player_id
    game.announcements.append(f"{player.seat_number}号({player.name}) 自爆了！身份是狼人！")

    # 清除当前阶段的进行中数据
    clear_votes(game_id)
    game.current_speaker_id = None
    game.speak_order.clear()
    game.speak_turn_submitted = False
    clear_deadline(game_id)

    # 检查胜负
    from app.domain.roles import get_preset_rule
    win_condition = get_preset_rule(game.room_settings.scene.preset, "win_condition")
    winner = _check_win_condition(game, win_condition)
    if winner:
        game.winner_faction = winner
        game.game_status = GameStatus.end

    return {
        "player_id": player_id,
        "player_name": seat_label(player),
        "winner_faction": game.winner_faction,
        "in_sheriff_election": game.game_status == GameStatus.sheriff_election,
    }


def clear_wolf_self_destruct(game_id: str) -> None:
    """清空自爆状态"""
    game = _get_game_or_raise(game_id)
    game.wolf_self_destructed = None
