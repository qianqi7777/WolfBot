"""
守卫角色行动模块
"""

from app.domain.enums import RoleType
from app.domain.roles import SKILL_REGISTRY


class GuardAction:
    """守卫夜间行动"""

    role_type = RoleType.guard

    @classmethod
    async def night_action(cls, judge, game) -> None:
        """守卫夜间行动：选择守护目标"""
        skill = SKILL_REGISTRY[RoleType.guard]
        alive_players = [p for p in game.players if p.is_alive and p.role == RoleType.guard]

        # 暗牌场：总是公告"守卫请睁眼"
        from app.domain.roles import get_preset
        try:
            preset = get_preset(game.room_settings.scene.preset)
            is_dark = preset.is_dark
        except ValueError:
            is_dark = True

        if is_dark or alive_players:
            await judge._announce(f"{skill.name}请睁眼，请选择要守护的目标")

        if not alive_players:
            if is_dark:
                import asyncio
                await asyncio.sleep(1.0)
            return

        # AI 守卫自动守护
        from app.services.ai_service import _generate_ai_night_action
        from app.services.game_service import record_night_action
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target, action_type = await _generate_ai_night_action(game.game_id, ai_p.id)
            if target:
                record_night_action(game.game_id, ai_p.id, target, action_type or "")

        # 通知真人守卫
        from app.domain.enums import MessageType
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            payload = {
                "actionRequired": True,
                "role": RoleType.guard.value,
                "hint": skill.human_hint,
            }
            await judge._send_to_player(human_p.id, MessageType.night_action, payload)

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """AI守卫选择守护目标"""
        import random
        from app.services.ai_service import _get_claimed_prophet

        targets = [p for p in game.players if p.is_alive]
        # 排除上次守护的人
        if player.last_guard_target_id:
            targets = [p for p in targets if p.id != player.last_guard_target_id]

        if not targets:
            return "", ""

        # 优先守警长
        if game.sheriff_id:
            sheriff_p = next((p for p in targets if p.id == game.sheriff_id), None)
            if sheriff_p and random.random() < 0.6:
                return sheriff_p.id, ""

        # 其次守自称预言家
        claimed_prophet = _get_claimed_prophet(game, targets)
        if claimed_prophet and random.random() < 0.5:
            return claimed_prophet.id, ""

        return random.choice(targets).id, ""
