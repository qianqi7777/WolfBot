"""
女巫角色行动模块
"""

from app.domain.enums import RoleType
from app.domain.roles import SKILL_REGISTRY


class WitchAction:
    """女巫夜间行动"""

    role_type = RoleType.witch

    @classmethod
    def _compute_wolf_kill_target(cls, game) -> str | None:
        """从已提交的狼人行动中统计刀口（多数票）"""
        wolf_targets = []
        for action in game.night_actions:
            if str(action.get("role", "")) == RoleType.wolf.value:
                wolf_targets.append(str(action.get("targetId", "")))
        if not wolf_targets:
            return None
        tally = {}
        for tid in wolf_targets:
            tally[tid] = tally.get(tid, 0) + 1
        return max(tally, key=tally.get)

    @classmethod
    async def night_action(cls, judge, game) -> None:
        """女巫夜间行动：使用解药/毒药"""
        skill = SKILL_REGISTRY[RoleType.witch]
        alive_players = [p for p in game.players if p.is_alive and p.role == RoleType.witch]

        # 暗牌场：总是公告"女巫请睁眼"
        from app.domain.roles import get_preset
        try:
            preset = get_preset(game.room_settings.scene.preset)
            is_dark = preset.is_dark
        except ValueError:
            is_dark = True

        if is_dark or alive_players:
            await judge._announce(f"{skill.name}请睁眼，请选择是否使用药剂")

        if not alive_players:
            if is_dark:
                import asyncio
                await asyncio.sleep(1.0)
            return

        # 计算狼人刀口
        witch_wolf_target_id = cls._compute_wolf_kill_target(game)

        # AI 女巫自动行动
        from app.services.ai_service import _generate_ai_night_action
        from app.services.game_service import record_night_action
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target, action_type = await _generate_ai_night_action(game.game_id, ai_p.id)
            if target:
                record_night_action(game.game_id, ai_p.id, target, action_type or "", witch_wolf_target_id)

        # 通知真人女巫
        from app.domain.enums import MessageType
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            is_first_night = game.current_round == 1
            self_save_hint = "（首夜可自救）" if is_first_night else "（不可自救）"
            payload = {
                "actionRequired": True,
                "role": RoleType.witch.value,
                "hint": skill.human_hint,
            }
            if witch_wolf_target_id:
                target_player = next((p for p in game.players if p.id == witch_wolf_target_id), None)
                wolf_victim_label = f"{target_player.seat_number}号({target_player.name})" if target_player else "无人"
                payload["wolfKillTargetId"] = witch_wolf_target_id
                payload["wolfKillTargetLabel"] = wolf_victim_label
                payload["hint"] = f"狼人今晚袭击了 {wolf_victim_label}，是否使用解药？{self_save_hint}你也可以使用毒药毒杀任意玩家。每晚只能使用一瓶药。"
            else:
                payload["hint"] = f"今晚无人被刀，你可以使用毒药毒杀任意玩家（或跳过）。{self_save_hint}"
            await judge._send_to_player(human_p.id, MessageType.night_action, payload)

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """AI女巫夜间行动"""
        import random
        from app.services.ai_service import _ai_witch_night_action
        return _ai_witch_night_action(game, player, cls._compute_wolf_kill_target(game))
