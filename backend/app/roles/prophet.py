"""
预言家角色行动模块
"""

from app.domain.enums import RoleType
from app.domain.roles import SKILL_REGISTRY


class ProphetAction:
    """预言家夜间行动"""

    role_type = RoleType.prophet

    @classmethod
    async def night_action(cls, judge, game) -> None:
        """预言家夜间行动：查验玩家身份"""
        skill = SKILL_REGISTRY[RoleType.prophet]
        alive_players = [p for p in game.players if p.is_alive and p.role == RoleType.prophet]

        # 暗牌场：总是公告"预言家请睁眼"
        from app.domain.roles import get_preset
        try:
            preset = get_preset(game.room_settings.scene.preset)
            is_dark = preset.is_dark
        except ValueError:
            is_dark = True

        if is_dark or alive_players:
            await judge._announce(f"{skill.name}请睁眼，请选择要查验的玩家")

        if not alive_players:
            if is_dark:
                import asyncio
                await asyncio.sleep(1.0)
            return

        # AI 预言家自动查验
        from app.services.ai_service import _generate_ai_night_action
        from app.services.game_service import record_night_action
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target, action_type = await _generate_ai_night_action(game.game_id, ai_p.id)
            if target:
                record_night_action(game.game_id, ai_p.id, target, action_type or "")

        # 通知真人预言家
        from app.domain.enums import MessageType
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            payload = {
                "actionRequired": True,
                "role": RoleType.prophet.value,
                "hint": skill.human_hint,
            }
            await judge._send_to_player(human_p.id, MessageType.night_action, payload)

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """AI预言家选择查验目标"""
        import random
        from app.services.ai_service import _get_suspicious_players

        targets = [p for p in game.players if p.is_alive and p.id != player.id]
        # 排除上次查验的人
        if player.last_prophet_target_id:
            targets = [p for p in targets if p.id != player.last_prophet_target_id]

        if not targets:
            return "", ""

        # 优先验可疑玩家
        suspicious = _get_suspicious_players(game, targets)
        if suspicious and random.random() < 0.7:
            return random.choice(suspicious).id, ""

        return random.choice(targets).id, ""
