"""
狼人角色行动模块
"""

from app.domain.enums import RoleType
from app.domain.roles import SKILL_REGISTRY


class WolfAction:
    """狼人夜间行动"""

    role_type = RoleType.wolf

    @classmethod
    async def night_action(cls, judge, game) -> None:
        """狼人夜间行动：选择击杀目标"""
        skill = SKILL_REGISTRY[RoleType.wolf]
        alive_players = [p for p in game.players if p.is_alive and p.role == RoleType.wolf]

        # 暗牌场：总是公告"狼人请睁眼"
        from app.domain.roles import get_preset
        try:
            preset = get_preset(game.room_settings.scene.preset)
            is_dark = preset.is_dark
        except ValueError:
            is_dark = True

        if is_dark or alive_players:
            await judge._announce(f"{skill.name}请睁眼，请选择要袭击的目标")

        if not alive_players:
            if is_dark:
                import asyncio
                await asyncio.sleep(1.0)
            return

        # AI 狼人自动选择击杀目标
        from app.services.ai_service import _generate_ai_night_action
        from app.services.game_service import record_night_action
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target, action_type = await _generate_ai_night_action(game.game_id, ai_p.id)
            if target:
                record_night_action(game.game_id, ai_p.id, target, action_type or "")

        # 通知真人狼人
        from app.schemas.socket import SocketMessage
        from app.domain.enums import MessageType
        from app.utils.time import utc_now_iso
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            teammates = [
                f"{t.seat_number}号" for t in game.players
                if SKILL_REGISTRY[t.role].faction == "wolf"
                and t.id != human_p.id
                and t.is_alive
            ]
            payload = {
                "actionRequired": True,
                "role": RoleType.wolf.value,
                "hint": skill.human_hint,
            }
            if teammates:
                payload["teammates"] = teammates
                payload["hint"] += f"\n你的狼人队友：{'、'.join(teammates)}"
            await judge._send_to_player(human_p.id, MessageType.night_action, payload)

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """AI狼人选择击杀目标"""
        import random
        targets = [p for p in game.players if p.is_alive and SKILL_REGISTRY[p.role].faction != "wolf"]
        if targets:
            return random.choice(targets).id, ""
        return "", ""
