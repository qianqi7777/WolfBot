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
            speech = await _generate_ai_speech(self.game_id, player.id)
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

        # 按注册表顺序依次询问各角色
        for role_type in get_night_action_roles():
            logger.info("[Judge] game=%s 询问 %s 行动", self.game_id, get_skill(role_type).name)
            await self._ask_role(game, role_type)
            await asyncio.sleep(0.5)

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
        return await self._announce_night_result(night_result)

    async def _ask_role(self, game, role_type: RoleType) -> None:
        """法官询问指定角色 — 通用方法，支持所有有夜间行动的角色"""
        skill = get_skill(role_type)
        alive_players = [
            p for p in game.players
            if p.is_alive and p.role == role_type
        ]
        if not alive_players:
            return

        await self._announce(f"{skill.name}请睁眼，请选择要行动的目标")

        # AI 玩家自动行动
        ai_players = [p for p in alive_players if p.is_ai]
        for ai_p in ai_players:
            target = await _generate_ai_night_action(self.game_id, ai_p.id)
            if target:
                record_night_action(self.game_id, ai_p.id, target)

        # 通知真人玩家提交行动
        human_players = [p for p in alive_players if not p.is_ai]
        for human_p in human_players:
            payload = {
                "actionRequired": True,
                "role": role_type.value,
                "hint": skill.human_hint,
            }
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

    async def _announce_night_result(self, night_result: dict[str, Any]) -> bool:
        """处理夜晚结算结果：标记死亡、发送night_result/player_update消息。
        死亡/平安夜公告移到 day_phase 开头统一公布。
        返回 True 表示游戏继续，False 表示结束。"""
        killed_id = night_result.get("killed_player_id")
        guarded_player_id = night_result.get("guarded_player_id")
        guard_blocked = night_result.get("guard_blocked", False)
        checked_results = night_result.get("checked_results", [])

        game = self._game()
        is_first_night = game.current_round == 1

        if killed_id:
            # 有人被杀：发送 night_result 和 player_update（不再发公告）
            killed_player = next(
                (p for p in self._game().players if p.id == killed_id), None
            )
            name = f"{killed_player.seat_number}号({killed_player.name})" if killed_player else "某玩家"
            await self._broadcast(MessageType.night_result, {
                "killedPlayerId": killed_id,
                "guardedPlayerId": guarded_player_id,
                "guardBlocked": guard_blocked,
                "checkedResults": checked_results,
            })
            await self._broadcast(MessageType.player_update, {
                "playerId": killed_id,
                "isAlive": False,
                "playerName": name,
            })
            # 遗言：根据模式决定是否允许（首夜/非首夜区分）
            allow_last_words = False
            if self._mode:
                allow_last_words = await self._mode.on_night_death(self.game_id, is_first_night)
            if allow_last_words and killed_player:
                await self._announce(f"{name} 可以发表遗言（首夜遗言）")
                await self._wait_last_words(killed_id, name, timeout_seconds=self._preset_rules.get("last_words_timeout_seconds", 30))
        elif guard_blocked:
            await self._broadcast(MessageType.night_result, {
                "killedPlayerId": None,
                "guardedPlayerId": guarded_player_id,
                "guardBlocked": True,
                "checkedResults": checked_results,
            })
        else:
            await self._broadcast(MessageType.night_result, {
                "killedPlayerId": None,
                "guardedPlayerId": None,
                "guardBlocked": False,
                "checkedResults": checked_results,
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

        # 检查胜负
        game = self._game()
        if game.winner_faction is not None:
            await self._broadcast_game_over()
            return False
        return True

    # ------------------------------------------------------------------
    #  白天阶段
    # ------------------------------------------------------------------

    async def day_phase(self) -> bool:
        """执行白天阶段（公告 → 遗言 → 发言 → 投票）。返回 True 继续，False 结束。"""
        game = self._game()

        # 天亮公告
        set_game_status(self.game_id, GameStatus.day)
        await self._broadcast(MessageType.game_status, {
            "status": GameStatus.day.value,
            "currentRound": game.current_round,
        })
        await self._announce("天亮了")

        # ── 汇总昨晚死亡/平安夜公告 ──
        # 从 night_result 提取信息
        night_result_data = getattr(self, '_last_night_result', None)
        if night_result_data:
            killed_id = night_result_data.get("killed_player_id")
            guard_blocked = night_result_data.get("guard_blocked", False)
            if killed_id:
                killed_player = next((p for p in game.players if p.id == killed_id), None)
                name = f"{killed_player.seat_number}号({killed_player.name})" if killed_player else "某玩家"
                if guard_blocked:
                    await self._announce(f"昨夜是平安夜（守卫成功守住对 {name} 的袭击）")
                else:
                    await self._announce(f"昨夜，{name} 被杀害")
            elif guard_blocked:
                await self._announce("昨夜是平安夜（守卫成功守住袭击）")
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

        # 投票阶段
        continue_game = await self.vote_phase()
        return continue_game

    # ------------------------------------------------------------------
    #  发言阶段
    # ------------------------------------------------------------------

    async def speak_phase(self) -> bool:
        """执行发言阶段。返回 True 继续，False 结束。"""
        set_game_status(self.game_id, GameStatus.speak)
        game = self._game()

        speak_order_rule = self._preset_rules.get("speak_order", "by_seat")
        current_speaker_id = begin_speak_turn(self.game_id, speak_order_rule)
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
                speech = await _generate_ai_speech(self.game_id, speaker.id)
                record_speak(self.game_id, speaker.id, speech)
                await self._broadcast(MessageType.ai_speak, {
                    "content": speech,
                    "playerId": speaker.id,
                    "playerName": f"{speaker.seat_number}号({speaker.name})",
                    "isAI": True,
                })
                await asyncio.sleep(0.2)
            else:
                # 真人发言：等待超时
                game_ref = self._game()
                speak_timeout = game_ref.room_settings.scene.speak_timeout_seconds
                end_time = asyncio.get_running_loop().time() + speak_timeout
                while asyncio.get_running_loop().time() < end_time:
                    current_game = self._game()
                    if current_game.speak_turn_submitted:
                        break
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

        # AI 投票
        for ai_player in list_ai_players(self.game_id):
            logger.info("[Judge] game=%s AI玩家 %s 投票中...", self.game_id, ai_player.name)
            target_id = await _generate_ai_vote(self.game_id, ai_player.id)
            record_vote(self.game_id, ai_player.id, target_id)
            await self._broadcast(MessageType.vote_result, {
                "voterId": ai_player.id,
                "targetId": target_id,
            })
            await asyncio.sleep(0.2)

        # 等待真人投票
        await asyncio.sleep(settings.ai_vote_window_seconds)

        # 结算投票
        clear_deadline(self.game_id)
        vote_tie_rule = self._preset_rules.get("vote_tie_rule", "no_elimination")
        result = resolve_vote_round(self.game_id, vote_tie_rule=vote_tie_rule)
        return await self._announce_vote_result(result)

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
            # 被放逐者发表遗言（由模式决定）
            allow_last_words = True
            if self._mode:
                allow_last_words = await self._mode.on_vote_elimination(self.game_id)
            if allow_last_words:
                await self._announce(f"{name} 可以发表遗言")
                await self._wait_last_words(eliminated_id, name, timeout_seconds=self._preset_rules.get("last_words_timeout_seconds", 30))
        elif idiot_immunity and eliminated_id_for_detail:
            # 白痴翻牌免疫
            immune_player = next(
                (p for p in self._game().players if p.id == eliminated_id_for_detail), None
            )
            name = f"{immune_player.seat_number}号({immune_player.name})" if immune_player else "某玩家"
            await self._announce(f"投票结果：{name} 被放逐，但翻牌白痴身份，免疫出局！之后不能投票。")
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
