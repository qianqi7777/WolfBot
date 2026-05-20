"""
游戏模式基类 — 模块化设计，方便扩展不同游戏模式。

每个模式定义流程钩子，Judge 调用钩子来执行模式特有的逻辑。
新增模式只需继承 BaseGameMode 并实现所需钩子即可。
"""

from __future__ import annotations

import abc
import random
from typing import Any

from app.domain.enums import GameStatus, RoleType


class BaseGameMode(abc.ABC):
    """游戏模式基类 — 所有模式必须继承此类"""

    @property
    @abc.abstractmethod
    def mode_id(self) -> str:
        """模式唯一标识，如 'classic', 'role_select'"""
        ...

    @property
    @abc.abstractmethod
    def mode_name(self) -> str:
        """模式中文名，如 '经典模式', '抢身份模式'"""
        ...

    @property
    def allow_role_select(self) -> bool:
        """是否支持抢身份阶段"""
        return False

    @property
    def role_select_timeout_seconds(self) -> int:
        """抢身份阶段超时秒数"""
        return 10

    @property
    def first_night_last_words(self) -> bool:
        """第一晚死亡是否有遗言"""
        return True

    @property
    def other_night_last_words(self) -> bool:
        """非首晚死亡是否有遗言"""
        return False

    @property
    def vote_last_words(self) -> bool:
        """投票淘汰是否有遗言"""
        return True

    async def on_game_start(self, game_id: str) -> GameStatus:
        """游戏开始时的钩子。返回初始游戏状态。"""
        return GameStatus.night

    async def on_role_select_start(self, game_id: str) -> dict[str, Any]:
        """抢身份阶段开始时调用。返回广播 payload。"""
        return {}

    async def resolve_role_selection(
        self,
        game_id: str,
        selections: dict[str, str],
        available_roles: list[RoleType],
    ) -> dict[str, RoleType]:
        """解决抢身份冲突。返回 {player_id: assigned_role}。

        selections: {player_id: chosen_role}
        available_roles: 可分配的角色列表（含重复）
        多个玩家抢同一角色时，优先随机分配，名额用完后剩余玩家随机分配。
        """
        result: dict[str, RoleType] = {}
        remaining_roles = list(available_roles)

        from collections import Counter
        role_quota: Counter[RoleType] = Counter(remaining_roles)
        role_applicants: dict[RoleType, list[str]] = {}
        for pid, role_str in selections.items():
            try:
                role = RoleType(role_str)
            except ValueError:
                continue
            role_applicants.setdefault(role, []).append(pid)

        assigned_players: set[str] = set()
        for role, applicants in role_applicants.items():
            available_slots = role_quota.get(role, 0)
            winners = random.sample(applicants, min(len(applicants), available_slots))
            for winner in winners:
                result[winner] = role
                remaining_roles.remove(role)
                assigned_players.add(winner)

        unassigned = [pid for pid in selections if pid not in assigned_players]
        random.shuffle(remaining_roles)
        for i, pid in enumerate(unassigned):
            if i < len(remaining_roles):
                result[pid] = remaining_roles[i]

        return result

    async def on_night_death(self, game_id: str, is_first_night: bool) -> bool:
        """夜间死亡时的钩子。返回是否允许遗言。"""
        return self.first_night_last_words if is_first_night else self.other_night_last_words

    async def on_vote_elimination(self, game_id: str) -> bool:
        """投票淘汰时的钩子。返回是否允许遗言。"""
        return self.vote_last_words

    async def on_day_start(self, game_id: str) -> list[str]:
        """白天开始时的额外公告列表"""
        return []


class ClassicMode(BaseGameMode):
    """经典模式 — 无抢身份，随机分配角色"""

    @property
    def mode_id(self) -> str:
        return "classic"

    @property
    def mode_name(self) -> str:
        return "经典模式"


class RoleSelectMode(BaseGameMode):
    """抢身份模式 — 开局前20秒抢身份"""

    @property
    def mode_id(self) -> str:
        return "role_select"

    @property
    def mode_name(self) -> str:
        return "抢身份模式"

    @property
    def allow_role_select(self) -> bool:
        return True

    @property
    def role_select_timeout_seconds(self) -> int:
        return 20

    async def on_game_start(self, game_id: str) -> GameStatus:
        """抢身份模式：先进入抢身份阶段"""
        return GameStatus.role_select

    async def on_role_select_start(self, game_id: str) -> dict[str, Any]:
        """抢身份阶段开始时，返回可抢角色列表"""
        from app.services.game_service import get_game_state
        from app.domain.roles import build_role_list

        game = get_game_state(game_id)
        preset = game.room_settings.scene.preset
        available_roles = build_role_list(preset)

        return {
            "availableRoles": [r.value for r in available_roles],
            "timeoutSeconds": self.role_select_timeout_seconds,
            "message": f"请选择你想要的身份，{self.role_select_timeout_seconds}秒后截止。多人抢同一身份将随机分配。",
        }

    async def on_day_start(self, game_id: str) -> list[str]:
        """白天开始时的额外公告"""
        from app.services.game_service import get_game_state
        game = get_game_state(game_id)
        alive_count = sum(1 for p in game.players if p.is_alive)
        return [f"当前存活人数：{alive_count}人"]


# ------------------------------------------------------------------
#  模式注册表
# ------------------------------------------------------------------

MODE_REGISTRY: dict[str, BaseGameMode] = {
    "classic": ClassicMode(),
    "role_select": RoleSelectMode(),
}


def get_mode(mode_id: str) -> BaseGameMode:
    """获取游戏模式实例"""
    if mode_id not in MODE_REGISTRY:
        raise ValueError(f"未知游戏模式: {mode_id}，可选: {list(MODE_REGISTRY.keys())}")
    return MODE_REGISTRY[mode_id]
