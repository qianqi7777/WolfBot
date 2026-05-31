"""
法官 (Judge) — 狼人杀游戏流程控制器

法官是整局游戏的"裁判"与"旁白"，负责：
1. 夜间按序询问各角色技能是否发动
2. 公布夜晚结果（谁死了 / 平安夜）
3. 主持白天发言（依次发言）
4. 主持投票并公布结果
5. 处理遗言、自爆等特殊规则
6. 判定胜负

所有广播消息都经过法官发出，保证流程清晰、阶段可追踪。
"""

import asyncio
import json
import logging
import random
from typing import Any

from app.domain.enums import GameStatus, MessageType, RoleType
from app.domain.roles import (
    SKILL_REGISTRY,
    get_skill,
    get_night_action_roles,
    get_preset_rule,
    DEFAULT_RULES,
    build_role_list,
)
from app.mode import get_mode, BaseGameMode
from app.schemas.socket import SocketMessage
from app.schemas.player import Player
from app.services.game_service import (
    advance_speak_turn,
    begin_speak_turn,
    clear_votes,
    clear_deadline,
    get_game_state,
    list_ai_players,
    list_alive_players,
    record_night_action,
    record_speak,
    record_sheriff_campaign_speak,
    record_last_words,
    record_vote,
    resolve_night,
    resolve_vote_round,
    set_deadline,
    set_game_status,
    _check_win_condition,
    record_role_selection,
    get_role_selections,
    clear_role_selections,
    assign_roles_from_selection,
    _assign_roles,
    _assign_seat_numbers,
    register_sheriff_campaign,
    withdraw_sheriff_campaign,
    record_sheriff_vote,
    resolve_sheriff_election,
    transfer_sheriff_badge,
    clear_sheriff_election,
    wolf_self_destruct,
    clear_wolf_self_destruct,
    seat_label,
)
from app.services.ai_service import (
    _generate_ai_speech,
    _generate_ai_vote,
    _generate_ai_night_action,
)
from app.core.config import settings
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

logger = logging.getLogger(__name__)


class Judge:
    """法官类 — 狼人杀游戏流程唯一控制器"""

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        self._preset_rules: dict[str, Any] = {}
        self._mode: BaseGameMode | None = None
        self._load_preset_rules()
        self._load_mode()

    def _load_preset_rules(self) -> None:
        """从场景预设加载规则"""
        game = get_game_state(self.game_id)
        preset_id = game.room_settings.scene.preset
        for key in DEFAULT_RULES:
            self._preset_rules[key] = get_preset_rule(preset_id, key)

    def _load_mode(self) -> None:
        """加载游戏模式"""
        game = get_game_state(self.game_id)
        mode_id = game.game_mode
        try:
            self._mode = get_mode(mode_id)
        except ValueError:
            self._mode = get_mode("classic")

    # ------------------------------------------------------------------
    #  工具方法
    # ------------------------------------------------------------------

    def _game(self):
        """获取最新游戏状态"""
        return get_game_state(self.game_id)

    async def _broadcast(self, msg_type: MessageType, payload: dict[str, Any]) -> None:
        """广播一条消息"""
        await manager.broadcast(
            self.game_id,
            SocketMessage(
                type=msg_type,
                timestamp=utc_now_iso(),
                payload=payload,
            ).model_dump_json(),
        )

    async def _announce(self, content: str) -> None:
        """法官公告"""
        await self._broadcast(MessageType.announce, {"content": content})

    async def _send_to_player(self, player_id: str, msg_type: MessageType, payload: dict[str, Any]) -> None:
        """向指定玩家私发消息"""
        msg = SocketMessage(
            type=msg_type,
            timestamp=utc_now_iso(),
            payload=payload,
        ).model_dump_json()
        await manager.send_to_player(self.game_id, player_id, msg)

    async def _wait_last_words(self, player_id: str, player_name: str, timeout_seconds: int = 30) -> None:
        """等待玩家发表遗言。设置 current_speaker_id 允许死亡玩家发言。"""
        game = self._game()
        game.current_speaker_id = player_id
        game.speak_turn_submitted = False

        # 设置遗言阶段状态（复用 day 状态，前端通过 currentSpeakerId 判断）
        deadline = set_deadline(self.game_id, timeout_seconds)

        await self._broadcast(MessageType.speak_turn, {
            "currentSpeakerId": player_id,
            "currentSpeakerName": f"{player_name}【遗言】",
            "turnIndex": 0,
            "turnCount": 1,
            "deadline": deadline,
            "totalSeconds": timeout_seconds,
            "isLastWords": True,
        })

        # AI 死亡玩家自动发表遗言
        player = next((p for p in game.players if p.id == player_id), None)
        if player and player.is_ai:
            speech = await _generate_ai_speech(self.game_id, player.id, speech_type="last_words")
            record_last_words(self.game_id, player.id, speech)
            await self._broadcast(MessageType.ai_speak, {
                "content": speech,
                "playerId": player.id,
                "playerName": f"{player.seat_number}号({player.name})【遗言】",
                "isAI": True,
            })
            clear_deadline(self.game_id)
            game.current_speaker_id = None
            game.speak_turn_submitted = False
            return

        # 等待真人遗言
        logger.info("[Judge] game=%s 等待 %s 遗言，超时=%ds", self.game_id, player_name, timeout_seconds)
        end_time = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < end_time:
            current_game = self._game()
            if current_game.speak_turn_submitted:
                break
            await asyncio.sleep(0.25)

        clear_deadline(self.game_id)
        game.current_speaker_id = None
        game.speak_turn_submitted = False

    # ------------------------------------------------------------------
    #  猎人开枪处理
    # ------------------------------------------------------------------

    def _check_hunter_last_god(self) -> bool:
        """检查猎人是否是最后存活的神职（灵牌）。
        如果猎人是最后一个神职，开枪会直接触发屠边导致狼人获胜，因此不能开枪。
        返回 True 表示猎人是最后神职（不能开枪），False 表示不是（可以开枪）。"""
        game = self._game()
        hunter_id = game.pending_hunter_shoot
        if not hunter_id:
            return False

        # 神职角色列表
        god_roles = {RoleType.prophet, RoleType.witch, RoleType.hunter, RoleType.guard, RoleType.idiot}

        # 获取所有存活的神职（排除猎人自己，因为猎人已死亡/即将出局）
        alive_gods = [
            p for p in game.players
            if p.is_alive and p.role in god_roles and p.id != hunter_id
        ]

        # 如果除猎人外没有存活神职 → 猎人是最后神职
        return len(alive_gods) == 0

    async def _handle_hunter_shoot(self) -> bool:
        """处理猎人开枪。猎人死亡后可以选择开枪带走一人。
        返回 True 继续，False 结束游戏。"""
        game = self._game()
        hunter_id = game.pending_hunter_shoot
        if not hunter_id:
            return True

        # 检查猎人是否是最后神职
        if self._check_hunter_last_god():
            hunter = next((p for p in game.players if p.id == hunter_id), None)
            hunter_name = f"{hunter.seat_number}号({hunter.name})" if hunter else "猎人"
            await self._announce(f"猎人是最后存活的灵牌(神职)，不能开枪，否则会直接触发屠边导致狼人获胜")
            game.pending_hunter_shoot = None
            return True

        logger.info("[Judge] game=%s 猎人 %s 触发开枪", self.game_id, hunter_id)
        hunter = next((p for p in game.players if p.id == hunter_id), None)
        if not hunter:
            game.pending_hunter_shoot = None
            return True

        hunter_name = f"{hunter.seat_number}号({hunter.name})"
        await self._announce(f"🔫 {hunter_name}（猎人）死亡，可以开枪带走一名玩家！")
        # 公开广播猎人翻牌（合规公开身份）。
        # 使用 publicRole 而非 revealedRole 字段，避免与预言家私发查验结果冲突。
        await self._broadcast(MessageType.player_update, {
            "playerId": hunter_id,
            "playerName": hunter_name,
            "isAlive": False,
            "publicRole": "hunter",
        })

        # 获取可射击目标：存活玩家（不含自己）
        targets = [p for p in game.players if p.is_alive and p.id != hunter_id]
        if not targets:
            await self._announce("没有可射击的目标")
            game.pending_hunter_shoot = None
            return True

        shoot_timeout = 30

        if hunter.is_ai:
            # AI 猎人自动选择目标
            import random as _random
            # 策略1：优先射杀发言中被多人怀疑的玩家（从聊天推断）
            suspected_targets = self._ai_hunter_pick_target(game, hunter, targets)
            if suspected_targets and _random.random() < 0.6:
                target = suspected_targets
            # 策略2：从投票中找得票最多的玩家
            elif game.votes and _random.random() < 0.4:
                vote_tally: dict[str, int] = {}
                for v in game.votes:
                    tid = str(v.get("targetId", ""))
                    if tid and tid != "abstain":
                        vote_tally[tid] = vote_tally.get(tid, 0) + 1
                if vote_tally:
                    most_voted_id = max(vote_tally, key=vote_tally.get)
                    most_voted = next((p for p in targets if p.id == most_voted_id), None)
                    if most_voted:
                        target = most_voted
                    else:
                        target = _random.choice(targets)
                else:
                    target = _random.choice(targets)
            else:
                target = _random.choice(targets)

            target_name = f"{target.seat_number}号({target.name})"
            await self._announce(f"🔫 {hunter_name} 开枪带走了 {target_name}！")
            target.is_alive = False

            await self._broadcast(MessageType.player_update, {
                "playerId": target.id,
                "isAlive": False,
                "playerName": target_name,
            })
        else:
            # 真人猎人：设置回合并等待选择
            deadline = set_deadline(self.game_id, shoot_timeout)
            # 广播猎人开枪请求
            await self._broadcast(MessageType.announce, {
                "content": f"🔫 猎人请选择开枪目标（{shoot_timeout}秒）",
                "hunterShoot": True,
                "hunterId": hunter_id,
                "candidateIds": [p.id for p in targets],
                "deadline": deadline,
            })

            # 等待真人选择
            end_time = asyncio.get_running_loop().time() + shoot_timeout
            target = None
            while asyncio.get_running_loop().time() < end_time:
                current_game = self._game()
                if current_game.pending_hunter_shoot is None:
                    # 已处理（通过 WebSocket 消息设置）
                    break
                await asyncio.sleep(0.5)

            # 超时自动选择
            current_game = self._game()
            if current_game.pending_hunter_shoot:
                import random as _random
                target = _random.choice(targets)
                target_name = f"{target.seat_number}号({target.name})"
                await self._announce(f"🔫 超时未选择，{hunter_name} 自动开枪带走了 {target_name}！")
                target.is_alive = False
                await self._broadcast(MessageType.player_update, {
                    "playerId": target.id,
                    "isAlive": False,
                    "playerName": target_name,
                })

            clear_deadline(self.game_id)

        # 清除开枪状态
        game.pending_hunter_shoot = None

        # 检查被猎人带走的玩家是否是警长
        if target and game.sheriff_id == target.id:
            await self._handle_sheriff_death(target.id)

        # 检查胜负
        game = self._game()
        if game.winner_faction is not None:
            await self._broadcast_game_over()
            return False

        return True

    # ------------------------------------------------------------------
    #  抢身份阶段
    # ------------------------------------------------------------------

    async def role_select_phase(self) -> bool:
        """执行抢身份阶段。返回 True 表示成功进入下一阶段。"""
        game = self._game()
        set_game_status(self.game_id, GameStatus.role_select)

        # 广播抢身份开始
        payload = await self._mode.on_role_select_start(self.game_id)
        timeout_seconds = self._mode.role_select_timeout_seconds
        deadline = set_deadline(self.game_id, timeout_seconds)

        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.role_select.value,
            "currentRound": game.current_round,
        })
        await self._broadcast(MessageType.role_select_start, {
            **payload,
            "deadline": deadline,
            "totalSeconds": timeout_seconds,
        })
        await self._announce("抢身份阶段开始！请选择你想要的身份")

        # 等待真人选择（超时后自动结算）
        logger.info("[Judge] game=%s 等待抢身份选择，超时=%ds", self.game_id, timeout_seconds)
        await asyncio.sleep(timeout_seconds)
        clear_deadline(self.game_id)

        # 结算抢身份
        selections = get_role_selections(self.game_id)
        available_roles = build_role_list(game.room_settings.scene.preset)

        # AI玩家不参与抢身份，直接分配
        human_selections = {
            pid: role for pid, role in selections.items()
            if not next((p for p in game.players if p.id == pid), Player(id="", name="", seat_number=0, role=RoleType.unknown, is_ai=True, is_alive=True)).is_ai
        }

        # 解决冲突
        role_assignments = await self._mode.resolve_role_selection(
            self.game_id, human_selections, available_roles
        )

        # 将未抢到/未选择身份的人类玩家和AI玩家都分配剩余角色
        human_players = [p for p in game.players if not p.is_ai]
        unassigned_humans = [p for p in human_players if p.id not in role_assignments]
        ai_players = [p for p in game.players if p.is_ai]

        # 用计数法扣除已分配角色
        from collections import Counter
        assigned_counter: Counter[RoleType] = Counter(role_assignments.values())
        remaining_roles: list[RoleType] = []
        for r in available_roles:
            if assigned_counter[r] > 0:
                assigned_counter[r] -= 1  # 扣除一个
            else:
                remaining_roles.append(r)  # 剩余的留给未分配玩家
        import random
        random.shuffle(remaining_roles)

        # 先分配给未选择/未抢到的人类玩家
        idx = 0
        for p in unassigned_humans:
            if idx < len(remaining_roles):
                role_assignments[p.id] = remaining_roles[idx]
                idx += 1

        # 再分配给AI玩家
        for p in ai_players:
            if idx < len(remaining_roles):
                role_assignments[p.id] = remaining_roles[idx]
                idx += 1

        # 应用分配结果
        assign_roles_from_selection(self.game_id, role_assignments)

        # 公布抢身份结果
        result_details = []
        for pid, role in role_assignments.items():
            player = next((p for p in game.players if p.id == pid), None)
            if player and not player.is_ai:
                # 只公布真人玩家的角色（视角隔离，只公布自己）
                result_details.append({"playerId": pid, "assignedRole": role.value})

        await self._broadcast(MessageType.role_select_result, {
            "assignments": result_details,
            "message": "身份分配完成",
        })
        await self._announce("抢身份阶段结束，身份已分配")

        # 向每个真人玩家私发其角色
        for pid, role in role_assignments.items():
            player = next((p for p in game.players if p.id == pid), None)
            if player and not player.is_ai:
                skill = get_skill(role)
                await self._send_to_player(pid, MessageType.role_info, {
                    "role": role.value,
                    "hint": skill.human_hint,
                })
                # 狼人队友信息
                if skill.faction == "wolf":
                    teammates = [
                        f"{t.seat_number}号" for t in game.players
                        if SKILL_REGISTRY[t.role].faction == "wolf"
                        and t.id != pid
                        and t.is_alive
                    ]
                    if teammates:
                        await self._send_to_player(pid, MessageType.announce, {
                            "content": f"你的狼人队友：{'、'.join(teammates)}",
                        })

        clear_role_selections(self.game_id)

        # 进入夜间阶段
        set_game_status(self.game_id, GameStatus.night)
        return True

    # ------------------------------------------------------------------
    #  夜间阶段：按序询问各角色技能
    # ------------------------------------------------------------------

    async def night_phase(self) -> bool:
        """执行夜间阶段。返回 True 表示游戏继续，False 表示游戏结束。

        夜间流程：
        1. 广播"天黑请闭眼"
        2. 法官按注册表顺序依次询问各角色：
           - 根据角色技能注册表自动遍历所有有夜间行动的角色
        3. 结算夜晚
        4. 广播夜晚结果
        """
        game = self._game()
        set_game_status(self.game_id, GameStatus.night)

        # 天黑请闭眼
        night_timeout = self._preset_rules.get("night_action_timeout_seconds", 30)
        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.night.value,
            "currentRound": game.current_round,
            "totalSeconds": night_timeout,
        })
        await self._announce("天黑请闭眼")
        await asyncio.sleep(1.5)

        # 按板子配置的 active_roles 顺序依次询问各角色
        from app.roles import get_active_role_actions
        active_actions = get_active_role_actions(game.room_settings.scene.preset)
        for action_class in active_actions:
            logger.info("[Judge] game=%s 询问 %s 行动", self.game_id, action_class.role_type.value)
            await action_class.night_action(self, game)
            await asyncio.sleep(0.5)

        # 首夜额外环节：白痴确认身份 + 猎人确认开枪状态
        # （网易标准规则：首夜白痴和猎人需睁眼让法官确认身份/状态，非首夜跳过）
        if game.current_round == 1:
            await self._first_night_identity_check(game)

        # 等待真人玩家提交夜间行动
        await self._announce("请有夜间行动的玩家提交行动")
        night_timeout = self._preset_rules.get("night_action_timeout_seconds", 30)
        deadline = set_deadline(self.game_id, night_timeout)
        await self._broadcast(MessageType.night_action, {
            "actionRequired": True,
            "deadline": deadline,
            "totalSeconds": night_timeout,
        })

        game = self._game()
        logger.info("[Judge] game=%s 等待真人夜间行动，超时=%ds", self.game_id, night_timeout)
        await asyncio.sleep(night_timeout)
        clear_deadline(self.game_id)

        # 结算夜晚
        logger.info("[Judge] game=%s 结算夜晚", self.game_id)
        night_result = resolve_night(self.game_id)
        self._last_night_result = night_result  # 保存给 day_phase 使用
        continue_game = await self._announce_night_result(night_result)
        if not continue_game:
            return False
        # 猎人开枪（如果猎人被狼杀）
        continue_game = await self._handle_hunter_shoot()
        return continue_game

    async def _ask_role(self, game, role_type: RoleType) -> None:
        """法官询问指定角色 — 暗牌场：无论该角色是否存在，都要展示询问环节（防止角色推断）"""
        skill = get_skill(role_type)
        alive_players = [
            p for p in game.players
            if p.is_alive and p.role == role_type
        ]

        # 暗牌场：总是公告"X请睁眼"（即使该角色已死亡或不存在）
        from app.domain.roles import get_preset
        preset_id = game.room_settings.scene.preset
        try:
            preset = get_preset(preset_id)
            is_dark = preset.is_dark
        except ValueError:
            is_dark = True
        if is_dark or alive_players:
            await self._announce(f"{skill.name}请睁眼，请选择要行动的目标")

        if not alive_players:
            # 暗牌场：即使无人存活也要稍作等待（模拟）
            if is_dark:
                await asyncio.sleep(1.0)
            return

        # ── 女巫特殊处理：先计算狼人刀口 ──
        witch_wolf_target_id: str | None = None
        if role_type == RoleType.witch:
            witch_wolf_target_id = self._compute_wolf_kill_target(game)

        # AI 玩家自动行动
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target, action_type = await _generate_ai_night_action(self.game_id, ai_p.id)
            if target:
                record_night_action(self.game_id, ai_p.id, target, action_type or "", witch_wolf_target_id)

        # 通知真人玩家提交行动
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            payload: dict[str, Any] = {
                "actionRequired": True,
                "role": role_type.value,
                "hint": skill.human_hint,
            }
            # 女巫：告知刀口
            if role_type == RoleType.witch:
                is_first_night = game.current_round == 1
                self_save_hint = "（首夜可自救）" if is_first_night else "（不可自救）"
                if witch_wolf_target_id:
                    target_player = next((p for p in game.players if p.id == witch_wolf_target_id), None)
                    wolf_victim_label = f"{target_player.seat_number}号({target_player.name})" if target_player else "无人"
                    payload["wolfKillTargetId"] = witch_wolf_target_id
                    payload["wolfKillTargetLabel"] = wolf_victim_label
                    payload["hint"] = f"狼人今晚袭击了 {wolf_victim_label}，是否使用解药？{self_save_hint}你也可以使用毒药毒杀任意玩家。每晚只能使用一瓶药。"
                else:
                    payload["hint"] = f"今晚无人被刀，你可以使用毒药毒杀任意玩家（或跳过）。{self_save_hint}"
            # 狼人队友信息：真人狼人能看到同场存活的狼人队友
            if skill.faction == "wolf":
                teammates = [
                    f"{t.seat_number}号" for t in game.players
                    if SKILL_REGISTRY[t.role].faction == "wolf"
                    and t.id != human_p.id
                    and t.is_alive
                ]
                if teammates:
                    payload["teammates"] = teammates
                    payload["hint"] += f"\n你的狼人队友：{'、'.join(teammates)}"
            await self._send_to_player(human_p.id, MessageType.night_action, payload)

    def _compute_wolf_kill_target(self, game) -> str | None:
        """从已提交的狼人行动中统计刀口（多数票）。"""
        wolf_targets: list[str] = []
        for action in game.night_actions:
            if str(action.get("role", "")) == RoleType.wolf.value:
                wolf_targets.append(str(action.get("targetId", "")))
        if not wolf_targets:
            return None
        tally: dict[str, int] = {}
        for tid in wolf_targets:
            tally[tid] = tally.get(tid, 0) + 1
        return max(tally, key=tally.get)

    async def _first_night_identity_check(self, game) -> None:
        """首夜额外环节：白痴确认身份 + 猎人确认开枪状态。
        网易标准规则：首夜白痴和猎人需睁眼让法官确认身份/状态，无操作，非首夜跳过。"""
        # 白痴确认身份
        idiot_alive = [p for p in game.players if p.is_alive and p.role == RoleType.idiot]
        if idiot_alive:
            await self._announce("白痴请睁眼，请确认身份")
            await asyncio.sleep(2)
            await self._announce("白痴请闭眼")
            await asyncio.sleep(0.5)
        else:
            # 暗牌场：即使角色不存在也要模拟等待（防止角色推断）
            from app.domain.roles import get_preset
            preset_id = game.room_settings.scene.preset
            try:
                preset = get_preset(preset_id)
                is_dark = preset.is_dark
            except ValueError:
                is_dark = True
            if is_dark:
                await self._announce("白痴请睁眼，请确认身份")
                await asyncio.sleep(2)
                await self._announce("白痴请闭眼")
                await asyncio.sleep(0.5)

        # 猎人确认开枪状态
        hunter_alive = [p for p in game.players if p.is_alive and p.role == RoleType.hunter]
        if hunter_alive:
            hunter = hunter_alive[0]
            # 猎人首夜一定可以开枪（还没被毒的可能）
            can_shoot = not getattr(hunter, 'poisoned', False)
            await self._announce("猎人请睁眼")
            # 私密告知猎人开枪状态
            await self._send_to_player(hunter.id, MessageType.night_action, {
                "actionRequired": False,
                "role": RoleType.hunter.value,
                "hint": f"你的开枪状态：{'可以开枪' if can_shoot else '不可开枪'}",
            })
            await asyncio.sleep(2)
            await self._announce("猎人请闭眼")
            await asyncio.sleep(0.5)
        else:
            # 暗牌场模拟
            from app.domain.roles import get_preset
            preset_id = game.room_settings.scene.preset
            try:
                preset = get_preset(preset_id)
                is_dark = preset.is_dark
            except ValueError:
                is_dark = True
            if is_dark:
                await self._announce("猎人请睁眼")
                await asyncio.sleep(2)
                await self._announce("猎人请闭眼")
                await asyncio.sleep(0.5)

    async def _announce_night_result(self, night_result: dict[str, Any]) -> bool:
        """处理夜晚结算结果：标记死亡、发送night_result/player_update消息。
        死亡/平安夜公告移到 day_phase 开头统一公布。
        返回 True 表示游戏继续，False 表示结束。"""
        killed_id = night_result.get("killed_player_id")
        guarded_player_id = night_result.get("guarded_player_id")
        guard_blocked = night_result.get("guard_blocked", False)
        checked_results = night_result.get("checked_results", [])
        witch_saved = night_result.get("witch_saved", False)
        witch_saved_player_id = night_result.get("witch_saved_player_id")
        witch_poisoned_player_id = night_result.get("witch_poisoned_player_id")
        all_killed_ids: list[str] = night_result.get("all_killed_ids", [])

        game = self._game()
        is_first_night = game.current_round == 1

        # 发送 night_result 广播（汇总所有死亡信息）
        await self._broadcast(MessageType.night_result, {
            "killedPlayerId": killed_id,
            "guardedPlayerId": guarded_player_id,
            "guardBlocked": guard_blocked,
            "witchSaved": witch_saved,
            "witchSavedPlayerId": witch_saved_player_id,
            "witchPoisonedPlayerId": witch_poisoned_player_id,
            "allKilledIds": all_killed_ids,
        })

        # 发送 player_update 给每个死亡的玩家
        for dead_id in all_killed_ids:
            dead_player = next((p for p in self._game().players if p.id == dead_id), None)
            name = f"{dead_player.seat_number}号({dead_player.name})" if dead_player else "某玩家"
            await self._broadcast(MessageType.player_update, {
                "playerId": dead_id,
                "isAlive": False,
                "playerName": name,
            })

        # 遗言处理：为每个死亡玩家处理遗言。
        # 若夜间结算已直接触发胜负（game_status 切到 end），跳过遗言以免 record_last_words 拒收。
        already_ended = self._game().winner_faction is not None
        for dead_id in all_killed_ids:
            dead_player = next((p for p in self._game().players if p.id == dead_id), None)
            if not dead_player:
                continue
            name = f"{dead_player.seat_number}号({dead_player.name})"
            allow_last_words = False
            if is_first_night and game.current_round == 1 and game.sheriff_id is None:
                allow_last_words = False
            elif self._mode:
                allow_last_words = await self._mode.on_night_death(self.game_id, is_first_night)
            if allow_last_words and not already_ended:
                await self._announce(f"{name} 可以发表遗言（首夜遗言）")
                await self._wait_last_words(dead_id, name, timeout_seconds=self._preset_rules.get("last_words_timeout_seconds", 30))

        # 如果没有死亡，发送平安夜/守卫/女巫救活信息
        if not all_killed_ids:
            if witch_saved:
                saved_player = next((p for p in self._game().players if p.id == witch_saved_player_id), None)
                saved_name = f"{saved_player.seat_number}号({saved_player.name})" if saved_player else "某玩家"
                await self._broadcast(MessageType.night_result, {
                    "killedPlayerId": None,
                    "guardedPlayerId": guarded_player_id,
                    "guardBlocked": guard_blocked,
                    "witchSaved": True,
                    "witchSavedPlayerId": witch_saved_player_id,
                })
            elif guard_blocked:
                await self._broadcast(MessageType.night_result, {
                    "killedPlayerId": None,
                    "guardedPlayerId": guarded_player_id,
                    "guardBlocked": True,
                })
            else:
                await self._broadcast(MessageType.night_result, {
                    "killedPlayerId": None,
                    "guardedPlayerId": None,
                    "guardBlocked": False,
                })

        # 向预言家私发查验结果
        for check in checked_results:
            prophet_id = check.get("playerId")
            target_id = check.get("targetId")
            is_wolf = check.get("isWolf", False)
            target_player = next(
                (p for p in self._game().players if p.id == target_id), None
            )
            target_label = f"{target_player.seat_number}号" if target_player else "某玩家"
            result_text = "狼人" if is_wolf else "好人"
            await self._send_to_player(str(prophet_id), MessageType.announce, {
                "content": f"法官告知：{target_label} 的身份是 {result_text}",
            })
            if target_player:
                # 网易规则：预言家仅能查到「好人/狼人」阵营，不能查到具体角色（女巫/猎人/守卫等）
                faction_role = "wolf" if is_wolf else "civilian"
                await self._send_to_player(str(prophet_id), MessageType.player_update, {
                    "playerId": target_player.id,
                    "playerName": f"{target_player.seat_number}号({target_player.name})",
                    "isAlive": target_player.is_alive,
                    "revealedRole": faction_role,
                })

        # 检查胜负
        game = self._game()
        if game.winner_faction is not None:
            await self._broadcast_game_over()
            return False
        return True

    # ------------------------------------------------------------------
    #  警长竞选阶段（仅第一轮白天前）
    # ------------------------------------------------------------------

    async def sheriff_election_phase(self) -> bool:
        """执行警长竞选阶段。仅在第一轮白天前调用。
        流程：上警注册 → 竞选发言 → 投票 → 结果公告
        返回 True 继续，False 结束。"""
        game = self._game()
        set_game_status(self.game_id, GameStatus.sheriff_election)

        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.sheriff_election.value,
            "currentRound": game.current_round,
        })
        await self._announce("警长竞选阶段开始！请选择是否上警")

        # ── 阶段1：上警注册 ──
        campaign_timeout = 15  # 给真人足够时间
        deadline = set_deadline(self.game_id, campaign_timeout)
        await self._broadcast(MessageType.sheriff_elect_start, {
            "phase": "campaign",
            "deadline": deadline,
            "totalSeconds": campaign_timeout,
            "candidateIds": [],
        })

        # AI 玩家自动决定是否上警
        for ai_p in list_ai_players(self.game_id):
            # 神职和狼人更可能上警，平民较少上警
            should_run = self._ai_should_run_for_sheriff(ai_p)
            if should_run:
                register_sheriff_campaign(self.game_id, ai_p.id)

        # 等待真人上警
        logger.info("[Judge] game=%s 等待玩家上警，超时=%ds", self.game_id, campaign_timeout)
        await asyncio.sleep(campaign_timeout)
        clear_deadline(self.game_id)

        game = self._game()
        candidates = game.sheriff_candidate_ids
        await self._broadcast(MessageType.sheriff_campaign, {
            "action": "register_done",
            "candidateIds": candidates,
            "withdrewIds": game.sheriff_withdrew_ids,
        })

        if not candidates:
            await self._announce("无人上警，本局无警长")
            clear_sheriff_election(self.game_id)
            return True

        if len(candidates) == 1:
            # 只有一人上警，直接当选
            winner = next((p for p in game.players if p.id == candidates[0]), None)
            name = f"{winner.seat_number}号({winner.name})" if winner else "某玩家"
            result = resolve_sheriff_election(self.game_id)
            sheriff_id = result.get("sheriff_id")
            if sheriff_id:
                await self._announce(f"仅 {name} 上警，自动当选警长！")
                await self._broadcast(MessageType.sheriff_elect_result, {
                    "sheriffId": sheriff_id,
                    "isTie": False,
                    "message": f"{name} 当选警长",
                })
                await self._broadcast(MessageType.player_update, {
                    "playerId": sheriff_id,
                    "isAlive": True,
                    "playerName": name,
                    "isSheriff": True,
                })
            clear_sheriff_election(self.game_id)
            return True

        # ── 阶段2：竞选发言（候选人按上警顺序逆序发言） ──
        await self._announce(f"{'、'.join(self._candidate_labels(game))} 上警，开始竞选发言")
        # 竞选发言顺序：从最后一个上警的玩家开始逆序发言（网易标准规则）
        # sheriff_candidate_ids 是按上警时间追加的列表，逆序即为"最后上警的先发言"
        candidates_sorted = list(reversed(game.sheriff_candidate_ids))

        for turn_idx, candidate_id in enumerate(candidates_sorted):
            game = self._game()
            if game.winner_faction is not None:
                return False

            # 检查竞选阶段狼人自爆
            if game.wolf_self_destructed:
                continue_game = await self._handle_wolf_self_destruct(game.wolf_self_destructed, sheriff_election_round=1)
                return continue_game

            # 检查退选
            if candidate_id not in game.sheriff_candidate_ids:
                continue

            candidate = next((p for p in game.players if p.id == candidate_id), None)
            if not candidate:
                continue

            game.current_speaker_id = candidate_id
            game.sheriff_campaign_submitted = False

            speak_timeout = game.room_settings.scene.speak_timeout_seconds
            deadline = set_deadline(self.game_id, speak_timeout)
            await self._broadcast(MessageType.sheriff_speech_turn, {
                "currentSpeakerId": candidate_id,
                "currentSpeakerName": f"{candidate.seat_number}号({candidate.name})",
                "turnIndex": turn_idx + 1,
                "turnCount": len(game.sheriff_candidate_ids),
                "deadline": deadline,
                "totalSeconds": speak_timeout,
                "canWithdraw": True,  # 竞选发言期间可以退水
            })
            await self._announce(f"轮到 {candidate.seat_number}号({candidate.name}) 竞选发言")

            if candidate.is_ai:
                # AI 竞选发言前：AI 狼人可能在竞选阶段自爆
                if SKILL_REGISTRY[candidate.role].faction == "wolf" and self._ai_should_self_destruct(candidate):
                    wolf_self_destruct(self.game_id, candidate.id)
                    continue_game = await self._handle_wolf_self_destruct(candidate.id, sheriff_election_round=1)
                    return continue_game
                # AI 竞选发言
                speech = await self._generate_ai_sheriff_speech(candidate)
                record_sheriff_campaign_speak(self.game_id, candidate.id, speech)
                await self._broadcast(MessageType.ai_speak, {
                    "content": speech,
                    "playerId": candidate.id,
                    "playerName": f"{candidate.seat_number}号({candidate.name})【竞选】",
                    "isAI": True,
                })
                await asyncio.sleep(0.3)
            else:
                # 真人竞选发言：等待超时，期间检查狼人自爆
                end_time = asyncio.get_running_loop().time() + speak_timeout
                while asyncio.get_running_loop().time() < end_time:
                    current_game = self._game()
                    if current_game.sheriff_campaign_submitted:
                        break
                    # 检查真人狼人在竞选期间自爆
                    if current_game.wolf_self_destructed:
                        continue_game = await self._handle_wolf_self_destruct(current_game.wolf_self_destructed, sheriff_election_round=1)
                        return continue_game
                    await asyncio.sleep(0.25)

            clear_deadline(self.game_id)
            game.current_speaker_id = None
            game.sheriff_campaign_submitted = False

        # ── 阶段3：投票选举警长 ──
        game = self._game()
        # 重新获取候选人（可能有人退选了）
        final_candidates = list(game.sheriff_candidate_ids)
        if not final_candidates:
            await self._announce("所有候选人退选，本局无警长")
            clear_sheriff_election(self.game_id)
            return True

        await self._announce("竞选发言结束，请投票选举警长")

        vote_timeout = self._preset_rules.get("vote_timeout_seconds", 30)
        deadline = set_deadline(self.game_id, vote_timeout)
        await self._broadcast(MessageType.sheriff_vote, {
            "candidateIds": final_candidates,
            "deadline": deadline,
            "totalSeconds": vote_timeout,
        })

        if game.wolf_self_destructed:
            continue_game = await self._handle_wolf_self_destruct(game.wolf_self_destructed, sheriff_election_round=1)
            return continue_game

        # AI 投票（非候选人 AI，排除退水和已翻牌白痴）
        for ai_p in list_ai_players(self.game_id):
            if ai_p.id in game.sheriff_candidate_ids:
                continue
            if ai_p.id in game.sheriff_withdrew_ids:
                continue
            # 白痴翻牌后不能投票
            if ai_p.vote_immunity_used:
                continue
            target = self._ai_vote_for_sheriff(ai_p, final_candidates)
            if target:
                record_sheriff_vote(self.game_id, ai_p.id, target)
            await asyncio.sleep(0.2)

        # 等待真人投票（排除退水和已翻牌白痴）
        non_candidate_alive = [
            p for p in game.players
            if p.is_alive
            and p.id not in game.sheriff_candidate_ids
            and p.id not in game.sheriff_withdrew_ids
            and not p.is_ai
            and not p.vote_immunity_used
        ]
        end_time = asyncio.get_running_loop().time() + vote_timeout
        while asyncio.get_running_loop().time() < end_time:
            current_game = self._game()
            if current_game.wolf_self_destructed:
                continue_game = await self._handle_wolf_self_destruct(current_game.wolf_self_destructed, sheriff_election_round=1)
                return continue_game
            voted_ids = {str(v.get("voterId", "")) for v in current_game.sheriff_votes}
            if all(p.id in voted_ids for p in non_candidate_alive):
                break
            await asyncio.sleep(0.5)

        clear_deadline(self.game_id)

        # ── 结算 ──
        result = resolve_sheriff_election(self.game_id)
        sheriff_id = result.get("sheriff_id")
        is_tie = result.get("is_tie", False)

        if sheriff_id:
            sheriff_player = next((p for p in self._game().players if p.id == sheriff_id), None)
            name = f"{sheriff_player.seat_number}号({sheriff_player.name})" if sheriff_player else "某玩家"
            tally_lines = self._sheriff_vote_tally(self._game())
            await self._announce(f"投票结果：{name} 当选警长！{tally_lines}")
            await self._broadcast(MessageType.sheriff_elect_result, {
                "sheriffId": sheriff_id,
                "isTie": False,
                "message": f"{name} 当选警长",
            })
            await self._broadcast(MessageType.player_update, {
                "playerId": sheriff_id,
                "isAlive": True,
                "playerName": name,
                "isSheriff": True,
            })
            clear_sheriff_election(self.game_id)
            return True

        if is_tie and len(final_candidates) >= 2:
            # 平票：先让平票候选人 PK 发言，再投票（网易标准规则）
            tied_candidate_ids = [
                str(cid) for cid in result.get("top_candidates", []) if cid
            ]
            # 兜底：top_candidates 缺失时退化为所有 final_candidates
            if not tied_candidate_ids:
                tied_candidate_ids = list(final_candidates)

            tied_labels = [
                f"{p.seat_number}号({p.name})"
                for cid in tied_candidate_ids
                for p in self._game().players if p.id == cid
            ]
            await self._announce(
                f"投票平票（{', '.join(tied_labels)}），进入 PK 发言阶段"
            )
            game.sheriff_votes.clear()

            # ── PK 发言：仅平票候选人，每人 ≤10s ──
            pk_speak_timeout = min(game.room_settings.scene.speak_timeout_seconds, 10)
            for turn_idx, candidate_id in enumerate(tied_candidate_ids):
                current_game = self._game()
                if current_game.winner_faction is not None:
                    return False
                # 检查 PK 阶段狼人自爆
                if current_game.wolf_self_destructed:
                    continue_game = await self._handle_wolf_self_destruct(
                        current_game.wolf_self_destructed, sheriff_election_round=2,
                    )
                    return continue_game

                candidate = next(
                    (p for p in current_game.players if p.id == candidate_id), None,
                )
                if not candidate:
                    continue

                game.current_speaker_id = candidate_id
                game.sheriff_campaign_submitted = False

                deadline = set_deadline(self.game_id, pk_speak_timeout)
                await self._broadcast(MessageType.sheriff_speech_turn, {
                    "currentSpeakerId": candidate_id,
                    "currentSpeakerName": f"{candidate.seat_number}号({candidate.name})",
                    "turnIndex": turn_idx + 1,
                    "turnCount": len(tied_candidate_ids),
                    "deadline": deadline,
                    "totalSeconds": pk_speak_timeout,
                    "canWithdraw": False,  # PK 阶段不能再退水
                    "isPk": True,
                })
                await self._announce(
                    f"PK 发言 - 轮到 {candidate.seat_number}号({candidate.name}) 发言"
                )

                if candidate.is_ai:
                    speech = await self._generate_ai_sheriff_speech(candidate)
                    record_sheriff_campaign_speak(self.game_id, candidate.id, speech)
                    await self._broadcast(MessageType.ai_speak, {
                        "content": speech,
                        "playerId": candidate.id,
                        "playerName": f"{candidate.seat_number}号({candidate.name})【PK】",
                        "isAI": True,
                    })
                    await asyncio.sleep(0.3)
                else:
                    end_time = asyncio.get_running_loop().time() + pk_speak_timeout
                    while asyncio.get_running_loop().time() < end_time:
                        cg = self._game()
                        if cg.sheriff_campaign_submitted:
                            break
                        if cg.wolf_self_destructed:
                            continue_game = await self._handle_wolf_self_destruct(
                                cg.wolf_self_destructed, sheriff_election_round=2,
                            )
                            return continue_game
                        await asyncio.sleep(0.25)

                clear_deadline(self.game_id)
                game.current_speaker_id = None
                game.sheriff_campaign_submitted = False

            # ── 第二轮投票 ──
            await self._announce("PK 发言结束，请重新投票选举警长")
            vote_timeout = self._preset_rules.get("vote_timeout_seconds", 30)
            deadline = set_deadline(self.game_id, vote_timeout)
            await self._broadcast(MessageType.sheriff_vote, {
                "candidateIds": final_candidates,
                "deadline": deadline,
                "totalSeconds": vote_timeout,
            })

            if game.wolf_self_destructed:
                continue_game = await self._handle_wolf_self_destruct(
                    game.wolf_self_destructed, sheriff_election_round=2,
                )
                return continue_game

            for ai_p in list_ai_players(self.game_id):
                if ai_p.id in game.sheriff_candidate_ids:
                    continue
                if ai_p.id in game.sheriff_withdrew_ids:
                    continue
                # 白痴翻牌后不能投票
                if ai_p.vote_immunity_used:
                    continue
                target = self._ai_vote_for_sheriff(ai_p, final_candidates)
                if target:
                    record_sheriff_vote(self.game_id, ai_p.id, target)
                await asyncio.sleep(0.2)

            # 重新计算非候选人存活列表（已排除退水和已翻牌白痴）
            non_candidate_alive_r2 = [
                p for p in self._game().players
                if p.is_alive
                and p.id not in game.sheriff_candidate_ids
                and p.id not in game.sheriff_withdrew_ids
                and not p.is_ai
                and not p.vote_immunity_used
            ]
            end_time = asyncio.get_running_loop().time() + vote_timeout
            while asyncio.get_running_loop().time() < end_time:
                current_game = self._game()
                if current_game.wolf_self_destructed:
                    continue_game = await self._handle_wolf_self_destruct(
                        current_game.wolf_self_destructed, sheriff_election_round=2,
                    )
                    return continue_game
                voted_ids = {str(v.get("voterId", "")) for v in current_game.sheriff_votes}
                if all(p.id in voted_ids for p in non_candidate_alive_r2):
                    break
                await asyncio.sleep(0.5)
            clear_deadline(self.game_id)

            result = resolve_sheriff_election(self.game_id)
            sheriff_id = result.get("sheriff_id")
            is_tie = result.get("is_tie", False)

            if sheriff_id:
                sheriff_player = next((p for p in self._game().players if p.id == sheriff_id), None)
                name = f"{sheriff_player.seat_number}号({sheriff_player.name})" if sheriff_player else "某玩家"
                tally_lines = self._sheriff_vote_tally(self._game())
                await self._announce(f"第二轮投票结果：{name} 当选警长！{tally_lines}")
                await self._broadcast(MessageType.sheriff_elect_result, {
                    "sheriffId": sheriff_id,
                    "isTie": False,
                    "message": f"{name} 当选警长",
                })
                await self._broadcast(MessageType.player_update, {
                    "playerId": sheriff_id,
                    "isAlive": True,
                    "playerName": name,
                    "isSheriff": True,
                })
            else:
                await self._announce("两轮投票均平票，本局无警长")
                await self._broadcast(MessageType.sheriff_elect_result, {
                    "sheriffId": None,
                    "isTie": True,
                    "message": "平票，本局无警长",
                })
        else:
            await self._announce("投票平票，本局无警长")
            await self._broadcast(MessageType.sheriff_elect_result, {
                "sheriffId": None,
                "isTie": is_tie,
                "message": "本局无警长",
            })

        clear_sheriff_election(self.game_id)
        return True

    def _candidate_labels(self, game) -> list[str]:
        """获取候选人座位标签列表"""
        labels = []
        for cid in game.sheriff_candidate_ids:
            p = next((pl for pl in game.players if pl.id == cid), None)
            if p:
                labels.append(f"{p.seat_number}号({p.name})")
        return labels

    def _ai_hunter_pick_target(self, game, hunter, candidates: list):
        """AI 猎人选择开枪目标（Bug #15）。
        从聊天中推断被多人怀疑的玩家，优先开枪带走。
        返回最可疑的目标玩家，如果没有则返回 None。
        """
        import re
        suspicious_seat_counts: dict[int, int] = {}

        # 扫描近期发言，统计被怀疑的玩家
        for chat in game.chats[-20:]:
            content = str(chat.get("content", ""))
            # 匹配模式：X号可疑 / 怀疑X号 / X是狼 / 投X号
            patterns = [
                r'(\d+)号.*可疑',
                r'怀疑.*?(\d+)号',
                r'(\d+)号.*是狼',
                r'(\d+).*是狼',
                r'投.*?(\d+)号',
                r'(\d+)号.*有问题',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for seat_str in matches:
                    seat_num = int(seat_str)
                    # 不把猎人自己算进去
                    if seat_num != hunter.seat_number:
                        suspicious_seat_counts[seat_num] = suspicious_seat_counts.get(seat_num, 0) + 1

        # 按被怀疑次数排序，返回最可疑的目标
        for seat_num, _count in sorted(suspicious_seat_counts.items(), key=lambda x: -x[1]):
            matched = next((p for p in candidates if p.seat_number == seat_num), None)
            if matched:
                return matched

        return None

    def _ai_should_run_for_sheriff(self, player) -> bool:
        """AI 决定是否上警。神职和狼人更倾向上警。"""
        import random
        skill = get_skill(player.role)
        if skill.faction == "wolf":
            return random.random() < 0.3  # 狼人30%概率上警
        if player.role in (RoleType.prophet, RoleType.witch, RoleType.guard):
            return random.random() < 0.6  # 神职60%概率上警
        return random.random() < 0.15  # 平民/猎人/白痴15%概率上警

    async def _generate_ai_sheriff_speech(self, player) -> str:
        """AI 生成竞选警长发言。优先调用 AI API，失败时回退到模板。"""
        game = self._game()
        skill = get_skill(player.role)

        # 尝试调用 AI API 生成竞选发言
        try:
            speech = await _generate_ai_speech(self.game_id, player.id, speech_type="campaign")
            if speech and speech.strip():
                logger.info("[Judge] game=%s AI竞选发言使用API生成", self.game_id)
                return speech
        except Exception as exc:
            logger.warning("[Judge] game=%s AI竞选发言API失败，回退模板: %s", self.game_id, exc)

        # 回退到模板
        import random
        templates = [
            f"大家好，我是{player.seat_number}号，我觉得这局我应该当警长，请大家支持我。",
            f"各位好，{player.seat_number}号申请上警。我希望能带领好人阵营走向胜利。",
            f"我是{player.seat_number}号，我想竞选警长。如果有警长的话，发言会更有条理。",
        ]
        return random.choice(templates)

    def _ai_vote_for_sheriff(self, player, candidates: list[str]) -> str | None:
        """AI 投票选警长"""
        if not candidates:
            return None
        # 随机投一个候选人
        return random.choice(candidates)

    def _sheriff_vote_tally(self, game) -> str:
        """生成警长竞选投票统计文本"""
        tally: dict[str, int] = {}
        for v in game.sheriff_votes:
            tid = str(v.get("targetId", ""))
            if tid == "abstain":
                continue
            tally[tid] = tally.get(tid, 0) + 1
        lines = []
        for tid, count in sorted(tally.items(), key=lambda x: -x[1]):
            p = next((pl for pl in game.players if pl.id == tid), None)
            label = f"{p.seat_number}号({p.name})" if p else "某玩家"
            lines.append(f"{label}：{count}票")
        return f"（{'；'.join(lines)}）" if lines else ""

    async def _handle_sheriff_death(self, dead_player_id: str) -> None:
        """处理警长死亡：转让徽章"""
        game = self._game()
        if game.sheriff_id != dead_player_id:
            return

        dead_player = next((p for p in game.players if p.id == dead_player_id), None)
        name = f"{dead_player.seat_number}号({dead_player.name})" if dead_player else "某玩家"
        await self._announce(f"警长 {name} 死亡，需要转让警长徽章")

        if dead_player and dead_player.is_ai:
            # AI 警长自动转让给存活的好人
            alive_non_wolf = [
                p for p in game.players
                if p.is_alive and p.id != dead_player_id
                and SKILL_REGISTRY[p.role].faction == "civilian"
            ]
            if alive_non_wolf:
                target = random.choice(alive_non_wolf)
                transfer_sheriff_badge(self.game_id, dead_player_id, target.id)
                target_name = f"{target.seat_number}号({target.name})"
                await self._announce(f"警长徽章转让给 {target_name}")
                await self._broadcast(MessageType.sheriff_transfer, {
                    "fromPlayerId": dead_player_id,
                    "toPlayerId": target.id,
                    "toPlayerName": target_name,
                })
                await self._broadcast(MessageType.player_update, {
                    "playerId": target.id,
                    "isAlive": True,
                    "playerName": target_name,
                    "isSheriff": True,
                })
            else:
                # 没有存活的好人可以转让，转让给任意存活玩家
                alive_others = [
                    p for p in game.players
                    if p.is_alive and p.id != dead_player_id
                ]
                if alive_others:
                    target = random.choice(alive_others)
                    transfer_sheriff_badge(self.game_id, dead_player_id, target.id)
                    target_name = f"{target.seat_number}号({target.name})"
                    await self._announce(f"警长徽章转让给 {target_name}")
                    await self._broadcast(MessageType.sheriff_transfer, {
                        "fromPlayerId": dead_player_id,
                        "toPlayerId": target.id,
                        "toPlayerName": target_name,
                    })
                    await self._broadcast(MessageType.player_update, {
                        "playerId": target.id,
                        "isAlive": True,
                        "playerName": target_name,
                        "isSheriff": True,
                    })
                else:
                    # 无人可转让
                    game.sheriff_id = None
                    await self._announce("警长徽章无人可继承，本局后续无警长")
        else:
            # 真人警长：等待选择继承人
            alive_others = [
                p for p in game.players
                if p.is_alive and p.id != dead_player_id
            ]
            if not alive_others:
                game.sheriff_id = None
                return

            transfer_timeout = 30
            deadline = set_deadline(self.game_id, transfer_timeout)
            await self._broadcast(MessageType.sheriff_transfer, {
                "fromPlayerId": dead_player_id,
                "needsChoice": True,
                "candidateIds": [p.id for p in alive_others],
                "deadline": deadline,
                "totalSeconds": transfer_timeout,
            })

            # 等待真人选择
            end_time = asyncio.get_running_loop().time() + transfer_timeout
            original_sheriff_id = game.sheriff_id
            while asyncio.get_running_loop().time() < end_time:
                current_game = self._game()
                if current_game.sheriff_id != original_sheriff_id:
                    # 已转让
                    break
                await asyncio.sleep(0.5)

            clear_deadline(self.game_id)
            if game.sheriff_id == dead_player_id:
                # 超时未选择，自动转让
                if alive_others:
                    target = random.choice(alive_others)
                    transfer_sheriff_badge(self.game_id, dead_player_id, target.id)
                    target_name = f"{target.seat_number}号({target.name})"
                    await self._announce(f"警长超时未选择，徽章自动转让给 {target_name}")
                    await self._broadcast(MessageType.sheriff_transfer, {
                        "fromPlayerId": dead_player_id,
                        "toPlayerId": target.id,
                        "toPlayerName": target_name,
                    })
                    await self._broadcast(MessageType.player_update, {
                        "playerId": target.id,
                        "isAlive": True,
                        "playerName": target_name,
                        "isSheriff": True,
                    })

    # ------------------------------------------------------------------
    #  狼人自爆处理
    # ------------------------------------------------------------------

    async def _ask_sheriff_direction(self) -> str:
        """询问警长选择发言方向（left/right）。
        - 真人警长：广播 speak_direction_request，等待15秒，超时默认"right"
        - AI 警长：随机选择方向
        返回 "left" 或 "right"。"""
        game = self._game()
        sheriff_id = game.sheriff_id
        if not sheriff_id:
            return "right"

        sheriff = next((p for p in game.players if p.id == sheriff_id), None)
        if not sheriff:
            return "right"

        if sheriff.is_ai:
            # AI 警长随机选择方向
            direction = random.choice(["left", "right"])
            await self._announce(f"警长选择了{'逆时针' if direction == 'left' else '顺时针'}发言")
            return direction

        # 真人警长：广播选择请求
        game.speak_direction = None
        deadline = set_deadline(self.game_id, 15)
        await self._broadcast(MessageType.speak_direction_request, {
            "sheriffId": sheriff_id,
            "deadline": deadline,
            "totalSeconds": 15,
        })
        await self._announce("请警长选择发言方向（顺时针/逆时针）")

        # 等待15秒
        end_time = asyncio.get_running_loop().time() + 15
        while asyncio.get_running_loop().time() < end_time:
            current_game = self._game()
            if current_game.speak_direction is not None:
                break
            await asyncio.sleep(0.5)

        clear_deadline(self.game_id)
        direction = game.speak_direction or "right"
        # 重置以备下次使用
        game.speak_direction = None
        await self._announce(f"警长选择了{'逆时针' if direction == 'left' else '顺时针'}发言")
        return direction

    # ------------------------------------------------------------------
    #  狼人自爆处理（原有）

    async def _handle_wolf_self_destruct(self, player_id: str, sheriff_election_round: int | None = None) -> bool:
        """处理狼人自爆：公告 → 遗言 → 警长转让 → 进入夜晚。
        返回 True 表示游戏继续，False 表示游戏结束。"""
        game = self._game()
        player = next((p for p in game.players if p.id == player_id), None)
        if not player:
            return True
        name = seat_label(player)

        # 公告自爆
        await self._announce(f"⚠️ {name} 自爆了！身份是狼人！")
        await self._broadcast(MessageType.wolf_self_destruct, {
            "playerId": player_id,
            "playerName": name,
            "playerRole": "wolf",
        })
        await self._broadcast(MessageType.player_update, {
            "playerId": player_id,
            "isAlive": False,
            "playerName": name,
        })

        # 竞选阶段自爆：按竞选轮次区分处理
        in_sheriff_election = game.game_status == GameStatus.sheriff_election
        if in_sheriff_election:
            if sheriff_election_round == 2:
                # 第二轮投票自爆：警徽永久流失，本局无警长
                await self._announce("第二轮竞选投票阶段狼人自爆，警徽永久流失！本局无警长。")
                game.sheriff_id = None
                clear_sheriff_election(self.game_id)
            else:
                # 第一轮任意竞选环节自爆：直接跳到下一轮夜晚
                await self._announce("竞选阶段狼人自爆，本轮竞选终止，当日无警长。")
                clear_sheriff_election(self.game_id)
        else:
            # 非竞选阶段自爆：自爆狼人发表遗言。
            # 若自爆已直接触发胜负（record_self_destruct 把 game_status 切到 end），
            # 跳过遗言以免 record_last_words 拒收。
            if self._game().winner_faction is None:
                await self._announce(f"{name} 可以发表遗言")
                await self._wait_last_words(player_id, name, timeout_seconds=self._preset_rules.get("last_words_timeout_seconds", 30))

        # 警长转让：终局已无意义，跳过以免广播多余 UI 并阻塞
        if game.sheriff_id == player_id and self._game().winner_faction is None:
            await self._handle_sheriff_death(player_id)

        # 清除自爆状态
        clear_wolf_self_destruct(self.game_id)

        # 检查胜负
        game = self._game()
        if game.winner_faction is not None:
            await self._broadcast_game_over()
            return False

        # 跳过剩余白天流程，直接进入下一轮夜晚
        game.current_round += 1
        await self._announce(f"狼人自爆，跳过剩余白天流程，直接进入第{game.current_round}轮夜晚")

        # 更新 AI 压缩记忆
        self._update_round_memory({"eliminated": None, "wolf_self_destructed": player_id})

        return True

    def _ai_should_self_destruct(self, player) -> bool:
        """AI 狼人决定是否自爆。
        策略：只有在特定不利情况下才考虑自爆，正常情况下不自爆。

        网易狼人杀自爆规则：
        - 自爆目的：保护队友、打断发言节奏、避免被投票出局
        - 自爆时机：被预言家查验、即将被投票、队友暴露等
        - 自爆不应该是随机行为，而是战略决策
        """
        game = self._game()

        # 首先检查：只有狼人才能自爆
        if SKILL_REGISTRY[player.role].faction != "wolf":
            return False

        alive_wolves = [p for p in game.players if p.is_alive and SKILL_REGISTRY[p.role].faction == "wolf"]
        alive_non_wolves = [p for p in game.players if p.is_alive and SKILL_REGISTRY[p.role].faction != "wolf"]

        # 只剩1只狼时不自爆（自爆就输了）
        if len(alive_wolves) <= 1:
            return False

        # 正常情况下，AI狼人不应该自爆
        # 自爆应该是在特定压力下的战略选择，而不是随机行为
        # TODO: 未来可以根据以下情况考虑自爆：
        # 1. 被预言家查验后（需要记录查验信息）
        # 2. 发言内容暴露身份（需要分析发言内容）
        # 3. 即将被投票出局（需要预测投票结果）
        # 4. 队友已经暴露需要保护（需要分析场上信息）

        # 当前简化策略：极端劣势时极低概率自爆
        # 好人数量是狼人4倍以上，且轮次较后时，极低概率自爆
        if len(alive_non_wolves) >= len(alive_wolves) * 4 and game.current_round >= 3:
            return random.random() < 0.005  # 0.5%概率

        # 默认不自爆
        return False

    # ------------------------------------------------------------------
    #  白天阶段
    # ------------------------------------------------------------------

    async def day_phase(self) -> bool:
        """执行白天阶段（警长竞选(首日) → 公告死讯 → 遗言 → 发言 → 投票）。返回 True 继续，False 结束。"""
        game = self._game()

        # 天亮公告
        set_game_status(self.game_id, GameStatus.day)
        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.day.value,
            "currentRound": game.current_round,
        })
        await self._announce("天亮了")

        # ── 警长死亡处理：如果警长在夜间被杀，转让徽章 ──
        night_result_data = getattr(self, '_last_night_result', None)
        if night_result_data:
            all_killed = night_result_data.get("all_killed_ids", [])
            if game.sheriff_id and game.sheriff_id in all_killed:
                await self._handle_sheriff_death(game.sheriff_id)

        # ── 警长竞选（仅第一轮白天，在公布死讯之前） ──
        current_round_before = game.current_round
        if game.current_round == 1 and game.sheriff_id is None:
            continue_game = await self.sheriff_election_phase()
            if not continue_game:
                return False
            if game.current_round != current_round_before:
                return True

        await asyncio.sleep(0.5)

        # ── 汇总昨晚死亡/平安夜公告（警长竞选结束之后公布） ──
        # 暗牌场：平安夜不显示原因（防止推断身份）
        if night_result_data:
            all_killed = night_result_data.get("all_killed_ids", [])
            if all_killed:
                for killed_id in all_killed:
                    killed_player = next((p for p in game.players if p.id == killed_id), None)
                    name = f"{killed_player.seat_number}号({killed_player.name})" if killed_player else "某玩家"
                    await self._announce(f"昨夜，{name} 被杀害")
            else:
                await self._announce("昨夜是平安夜")

        # 公告存活人数
        alive_count = sum(1 for p in game.players if p.is_alive)
        await self._announce(f"当前存活人数：{alive_count}人")

        # 模式钩子：额外公告
        if self._mode:
            extra_announces = await self._mode.on_day_start(self.game_id)
            for msg in extra_announces:
                await self._announce(msg)

        await asyncio.sleep(1.5)

        # 发言阶段
        continue_game = await self.speak_phase()
        if not continue_game:
            return False
        if game.current_round != current_round_before:
            return True

        # 投票阶段
        continue_game = await self.vote_phase()
        if not continue_game:
            return False
        if game.current_round != current_round_before:
            return True

        return True

    # ------------------------------------------------------------------
    #  发言阶段
    # ------------------------------------------------------------------

    async def speak_phase(self) -> bool:
        """执行发言阶段。返回 True 继续，False 结束。"""
        set_game_status(self.game_id, GameStatus.speak)
        game = self._game()

        speak_order_rule = self._preset_rules.get("speak_order", "by_seat")

        # 确定发言方向和参数
        sheriff_id = game.sheriff_id
        first_dead_player_id = game.first_dead_player_id
        speak_direction: str | None = None

        if sheriff_id:
            # 有警长：询问发言方向
            speak_direction = await self._ask_sheriff_direction()

        current_speaker_id = begin_speak_turn(
            self.game_id,
            speak_order_rule,
            sheriff_id=sheriff_id,
            first_dead_player_id=first_dead_player_id,
            speak_direction=speak_direction,
        )
        speak_turn_ids = game.speak_order or [
            p.id for p in game.players if p.is_alive
        ]

        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.speak.value,
            "currentRound": game.current_round,
            "currentSpeakerId": current_speaker_id,
        })
        await self._announce("现在进入发言阶段，请依次发言")

        for turn_index, speaker_id in enumerate(speak_turn_ids):
            game = self._game()
            if game.winner_faction is not None:
                return False

            # 检查狼人自爆
            if game.wolf_self_destructed:
                continue_game = await self._handle_wolf_self_destruct(game.wolf_self_destructed)
                return continue_game

            game.current_speaker_id = speaker_id
            game.speak_turn_submitted = False
            speaker = next((p for p in game.players if p.id == speaker_id), None)

            speak_timeout = game.room_settings.scene.speak_timeout_seconds
            deadline = set_deadline(self.game_id, speak_timeout)
            await self._broadcast(MessageType.speak_turn, {
                "currentSpeakerId": speaker_id,
                "currentSpeakerName": speaker.name if speaker else "",
                "turnIndex": turn_index + 1,
                "turnCount": len(speak_turn_ids),
                "deadline": deadline,
                "totalSeconds": speak_timeout,
            })
            await self._announce(f"轮到 {speaker.seat_number}号({speaker.name}) 发言")

            if speaker and speaker.is_ai:
                # AI 发言
                logger.info("[Judge] game=%s AI玩家 %s 发言中...", self.game_id, speaker.name)
                # AI 狼人可能在此自爆
                if self._ai_should_self_destruct(speaker):
                    wolf_self_destruct(self.game_id, speaker.id)
                    continue_game = await self._handle_wolf_self_destruct(speaker.id)
                    return continue_game
                speech = await _generate_ai_speech(self.game_id, speaker.id, speech_type="day_speak")
                record_speak(self.game_id, speaker.id, speech)
                await self._broadcast(MessageType.ai_speak, {
                    "content": speech,
                    "playerId": speaker.id,
                    "playerName": f"{speaker.seat_number}号({speaker.name})",
                    "isAI": True,
                })
                await asyncio.sleep(0.2)
            else:
                # 真人发言：等待超时，期间检查狼人自爆
                game_ref = self._game()
                speak_timeout = game_ref.room_settings.scene.speak_timeout_seconds
                end_time = asyncio.get_running_loop().time() + speak_timeout
                while asyncio.get_running_loop().time() < end_time:
                    current_game = self._game()
                    if current_game.speak_turn_submitted:
                        break
                    # 检查真人狼人自爆
                    if current_game.wolf_self_destructed:
                        continue_game = await self._handle_wolf_self_destruct(current_game.wolf_self_destructed)
                        return continue_game
                    await asyncio.sleep(0.25)

            clear_deadline(self.game_id)
            advance_speak_turn(self.game_id)

        return True

    # ------------------------------------------------------------------
    #  投票阶段
    # ------------------------------------------------------------------

    async def vote_phase(self) -> bool:
        """执行投票阶段。返回 True 继续，False 结束。"""
        set_game_status(self.game_id, GameStatus.vote)
        game = self._game()

        vote_timeout = self._preset_rules.get("vote_timeout_seconds", 30)
        deadline = set_deadline(self.game_id, vote_timeout)
        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.vote.value,
            "currentRound": game.current_round,
            "deadline": deadline,
            "totalSeconds": vote_timeout,
        })
        await self._announce("现在进入投票阶段，请投票放逐一名玩家")

        # AI 投票（排除已翻牌的白痴）
        for ai_player in list_ai_players(self.game_id):
            # 白痴翻牌后不能投票
            if ai_player.vote_immunity_used:
                continue
            logger.info("[Judge] game=%s AI玩家 %s 投票中...", self.game_id, ai_player.name)
            target_id = await _generate_ai_vote(self.game_id, ai_player.id)
            record_vote(self.game_id, ai_player.id, target_id)
            await self._broadcast(MessageType.vote_result, {
                "voterId": ai_player.id,
                "targetId": target_id,
            })
            await asyncio.sleep(0.2)

        # 等待真人投票（轮询检查是否全部完成，超时上限 vote_timeout）
        # 同时检查狼人自爆
        human_voters = [
            p for p in game.players
            if not p.is_ai and p.is_alive and not p.vote_immunity_used
        ]
        voted_ids = {str(v.get("voterId", "")) for v in self._game().votes}
        all_human_voted = all(p.id in voted_ids for p in human_voters)

        end_time = asyncio.get_running_loop().time() + vote_timeout
        while not all_human_voted and asyncio.get_running_loop().time() < end_time:
            await asyncio.sleep(0.5)
            current_game = self._game()
            # 检查狼人自爆
            if current_game.wolf_self_destructed:
                continue_game = await self._handle_wolf_self_destruct(current_game.wolf_self_destructed)
                return continue_game
            voted_ids = {str(v.get("voterId", "")) for v in current_game.votes}
            all_human_voted = all(p.id in voted_ids for p in human_voters)

        # 结算投票
        clear_deadline(self.game_id)
        vote_tie_rule = self._preset_rules.get("vote_tie_rule", "no_elimination")
        result = resolve_vote_round(self.game_id, vote_tie_rule=vote_tie_rule)
        continue_game = await self._announce_vote_result(result)
        if not continue_game:
            return False
        # 猎人开枪（如果猎人被投票放逐）
        continue_game = await self._handle_hunter_shoot()
        return continue_game

    async def _announce_vote_result(self, result: dict[str, Any]) -> bool:
        """公布投票结果。返回 True 继续，False 结束。"""
        eliminated_id = result.get("eliminated")
        idiot_immunity = result.get("idiot_immunity", False)
        eliminated_id_for_detail = result.get("eliminated_id_for_detail")
        winner_faction = result.get("winnerFaction")
        game = self._game()
        seat_map = {p.id: p.seat_number for p in game.players}

        # ── 广播投票明细（谁投了谁，含弃票） ──
        vote_detail = []
        for v in game.votes:
            voter_id = str(v.get("voterId", ""))
            target_id = str(v.get("targetId", ""))
            voter_seat = seat_map.get(voter_id)
            target_seat = seat_map.get(target_id) if target_id != "abstain" else None
            vote_detail.append({
                "voterId": voter_id,
                "voterSeat": voter_seat,
                "targetId": target_id,
                "targetSeat": target_seat,
            })
        await self._broadcast(MessageType.vote_summary, {
            "votes": vote_detail,
            "eliminated": eliminated_id,
        })

        # ── 统计被投票数（弃票不计入） ──
        tally: dict[str, int] = {}
        for v in game.votes:
            tid = str(v.get("targetId", ""))
            if tid == "abstain":
                continue
            tally[tid] = tally.get(tid, 0) + 1

        # 公布票数统计
        tally_lines = []
        for tid, count in sorted(tally.items(), key=lambda x: -x[1]):
            t_seat = seat_map.get(tid)
            t_player = next((p for p in self._game().players if p.id == tid), None)
            label = f"{t_seat}号({t_player.name})" if t_seat and t_player else "某玩家"
            # 列出投了该目标的玩家
            voter_names = []
            for v in game.votes:
                if str(v.get("targetId", "")) == tid:
                    voter_id = str(v.get("voterId", ""))
                    voter = next((p for p in self._game().players if p.id == voter_id), None)
                    if voter:
                        voter_names.append(f"{voter.seat_number}号({voter.name})")
            voter_info = f"（{', '.join(voter_names)}投）" if voter_names else ""
            tally_lines.append(f"{label}：{count}票{voter_info}")
        # 弃票信息
        abstain_voters = []
        for v in game.votes:
            if str(v.get("targetId", "")) == "abstain":
                voter_id = str(v.get("voterId", ""))
                voter = next((p for p in self._game().players if p.id == voter_id), None)
                if voter:
                    abstain_voters.append(f"{voter.seat_number}号({voter.name})")
        if abstain_voters:
            tally_lines.append(f"弃票：{', '.join(abstain_voters)}")
        if tally_lines:
            await self._announce("投票统计：" + "；".join(tally_lines))

        if eliminated_id:
            eliminated = next(
                (p for p in self._game().players if p.id == eliminated_id), None
            )
            name = f"{eliminated.seat_number}号({eliminated.name})" if eliminated else "某玩家"
            await self._announce(f"投票结果：{name} 被放逐")
            await self._broadcast(MessageType.player_update, {
                "playerId": eliminated_id,
                "isAlive": False,
                "playerName": name,
            })
            # 被放逐者发表遗言（由模式决定）。若该次放逐已直接触发胜负，
            # 游戏状态会被切到 end，此时遗言阶段已无意义且 record_last_words 会拒收，跳过。
            allow_last_words = True
            if self._mode:
                allow_last_words = await self._mode.on_vote_elimination(self.game_id)
            if allow_last_words and not winner_faction:
                await self._announce(f"{name} 可以发表遗言")
                await self._wait_last_words(eliminated_id, name, timeout_seconds=self._preset_rules.get("last_words_timeout_seconds", 30))
            # 警长被放逐：转让徽章。终局已无意义，跳过以免广播多余 UI 并阻塞 30s 等待。
            if eliminated and game.sheriff_id == eliminated_id and not winner_faction:
                await self._handle_sheriff_death(eliminated_id)
        elif idiot_immunity and eliminated_id_for_detail:
            # 白痴翻牌免疫
            immune_player = next(
                (p for p in self._game().players if p.id == eliminated_id_for_detail), None
            )
            name = f"{immune_player.seat_number}号({immune_player.name})" if immune_player else "某玩家"
            await self._announce(f"投票结果：{name} 被放逐，但翻牌白痴身份，免疫出局！之后不能投票。")
            # 公开广播白痴翻牌（合规公开身份，白痴仍存活）。
            # 使用 publicRole 而非 revealedRole 字段，避免与预言家私发查验结果冲突。
            await self._broadcast(MessageType.player_update, {
                "playerId": eliminated_id_for_detail,
                "playerName": name,
                "isAlive": True,
                "publicRole": "idiot",
                "isIdiotRevealed": True,
            })
        else:
            # 平票或无人出局
            if result.get("gameStatus") == GameStatus.night:
                await self._announce("投票平票，无人出局，直接进入黑夜")
            else:
                await self._announce("投票结束，无人出局")

        # ── 更新 AI 压缩记忆：本轮摘要 + 事件 ──
        self._update_round_memory(result)

        if winner_faction:
            await self._broadcast_game_over()
            # 游戏结束，清理记忆
            self._cleanup_memory()
            return False

        clear_votes(self.game_id)
        await asyncio.sleep(0.75)
        return True

    # ------------------------------------------------------------------
    #  游戏结束
    # ------------------------------------------------------------------

    async def _broadcast_game_over(self) -> None:
        """广播游戏结束"""
        game = self._game()
        faction_name = "好人阵营" if game.winner_faction == "civilian" else "狼人阵营"
        await self._announce(f"游戏结束，{faction_name}获得胜利！")
        await self._broadcast(MessageType.game_over, {
            "gameId": self.game_id,
            "winnerFaction": game.winner_faction,
            "currentRound": game.current_round,
            "players": [p.model_dump(by_alias=True) for p in game.players],
            "chats": game.chats,
            "announcements": game.announcements,
        })

    # ------------------------------------------------------------------
    #  压缩记忆管理
    # ------------------------------------------------------------------

    def _update_round_memory(self, vote_result: dict[str, Any]) -> None:
        """每轮结束后更新所有 AI 玩家的压缩记忆"""
        from app.services.memory_service import (
            memory_manager,
            update_structured_memory_from_game,
            build_round_summary_text,
        )

        game = self._game()
        # 构建本轮摘要
        eliminated_name = None
        eliminated_id = vote_result.get("eliminated")
        if eliminated_id:
            ep = next((p for p in game.players if p.id == eliminated_id), None)
            eliminated_name = f"{ep.seat_number}号" if ep else None

        # 从 announcements 提取夜晚死亡信息
        night_killed = None
        guard_blocked = False
        for ann in game.announcements:
            if "被杀害" in ann:
                # 提取信息（公告已用座位号，如"3号玩家被杀害"）
                night_killed = ann.replace("昨夜，", "").replace(" 被杀害", "").strip()
            if "守卫成功守住" in ann:
                guard_blocked = True

        # 从 chats 取本轮发言（用座位号标识）
        seat_map = {p.id: p.seat_number for p in game.players}
        speeches = []
        for chat in game.chats:
            speaker_id = str(chat.get("playerId", ""))
            seat = seat_map.get(speaker_id)
            speaker_label = f"{seat}号" if seat else str(chat.get("playerName", "?"))
            speeches.append({
                "speaker": speaker_label,
                "content": str(chat.get("content", "")),
            })

        round_summary = build_round_summary_text(
            round_no=game.current_round,
            night_killed=night_killed,
            guard_blocked=guard_blocked,
            speeches=speeches,
            vote_result=eliminated_id,
            eliminated_name=eliminated_name,
        )

        # 更新每个 AI 玩家的记忆
        for p in game.players:
            if not p.is_ai:
                continue
            store = memory_manager.get_or_create(self.game_id, p.id, p.name, p.role)
            update_structured_memory_from_game(store, game.players, self.game_id)
            store.set_round_summary(round_summary)

            # 关键事件
            if night_killed:
                store.record_event(f"N{game.current_round}：{night_killed}被杀")
            if guard_blocked:
                store.record_event(f"N{game.current_round}：守卫守住")
            if eliminated_name:
                store.record_event(f"D{game.current_round}：放逐{eliminated_name}")

            # 阶段摘要（每3轮合并）
            if game.current_round % 3 == 0 and store.layered_summary.round_summaries:
                recent = store.layered_summary.round_summaries[-3:]
                store.set_phase_summary("；".join(recent))

            # 全局摘要（游戏过半）
            if game.current_round >= 4 and not store.layered_summary.global_summary:
                store.set_global_summary(
                    f"第{game.current_round}轮，存活{sum(1 for pp in game.players if pp.is_alive)}人，"
                    f"已淘汰{sum(1 for pp in game.players if not pp.is_alive)}人"
                )

    def _cleanup_memory(self) -> None:
        """游戏结束后清理记忆"""
        from app.services.memory_service import memory_manager
        memory_manager.cleanup_game(self.game_id)

    # ------------------------------------------------------------------
    #  主循环
    # ------------------------------------------------------------------

    async def run_game(self) -> None:
        """运行整局游戏的主循环"""
        game = self._game()
        if game.ai_cycle_running or game.winner_faction is not None:
            logger.warning("[Judge] game=%s 游戏已在运行或已结束，跳过", self.game_id)
            return

        game.ai_cycle_running = True
        logger.info("[Judge] game=%s 游戏循环启动, 模式=%s", self.game_id, game.game_mode)
        try:
            # 抢身份阶段（如果模式支持）
            if self._mode and self._mode.allow_role_select and game.game_status == GameStatus.role_select:
                try:
                    continue_game = await self.role_select_phase()
                    if not continue_game:
                        return
                except Exception as exc:
                    logger.exception("[Judge] game=%s 抢身份阶段异常: %s", self.game_id, exc)
                    return

            max_rounds = self._preset_rules.get("max_rounds", 10)
            while game.current_round <= max_rounds:
                game = self._game()
                if game.winner_faction is not None:
                    break

                logger.info("[Judge] game=%s 第%d轮开始 — 夜间阶段", self.game_id, game.current_round)

                # 夜间
                try:
                    continue_game = await self.night_phase()
                except Exception as exc:
                    logger.exception("[Judge] game=%s 夜间阶段异常: %s", self.game_id, exc)
                    break
                if not continue_game:
                    break

                logger.info("[Judge] game=%s 第%d轮 — 白天阶段", self.game_id, game.current_round)

                # 白天
                try:
                    continue_game = await self.day_phase()
                except Exception as exc:
                    logger.exception("[Judge] game=%s 白天阶段异常: %s", self.game_id, exc)
                    break
                if not continue_game:
                    break

        except Exception:
            logger.exception("[Judge] game=%s 游戏循环异常退出", self.game_id)
        finally:
            game = self._game()
            game.ai_cycle_running = False
            logger.info("[Judge] game=%s 游戏循环结束", self.game_id)
