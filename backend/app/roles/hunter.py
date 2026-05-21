"""
猎人角色行动模块
"""

from app.domain.enums import RoleType


class HunterAction:
    """猎人角色行动（主要处理白天开枪逻辑）"""

    role_type = RoleType.hunter

    @classmethod
    async def day_action(cls, judge, game) -> None:
        """猎人白天行动：处理开枪"""
        # 猎人的开枪逻辑在 judge_service._handle_hunter_shoot 中处理
        # 这里可以扩展为更复杂的猎人逻辑
        pass

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """猎人没有夜间行动"""
        return "", ""
