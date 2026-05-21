"""
白痴角色行动模块
"""

from app.domain.enums import RoleType


class IdiotAction:
    """白痴角色行动（主要处理翻牌免疫逻辑）"""

    role_type = RoleType.idiot

    @classmethod
    async def day_action(cls, judge, game) -> None:
        """白痴白天行动：处理翻牌免疫"""
        # 白痴的翻牌逻辑在 game_service.resolve_vote_round 中处理
        # 这里可以扩展为更复杂的白痴逻辑
        pass

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """白痴没有夜间行动"""
        return "", ""
