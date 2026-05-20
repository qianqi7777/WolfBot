import asyncio
import json
import logging
import random
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.enums import GameStatus, MessageType, RoleType
from app.domain.roles import get_skill, get_mock_speech, SKILL_REGISTRY
from app.schemas.socket import SocketMessage
from app.services.game_service import (
    AiRuntimeConfig,
    advance_speak_turn,
    begin_speak_turn,
    clear_votes,
    get_game_state,
    list_ai_players,
    list_alive_players,
    record_night_action,
    record_speak,
    record_vote,
    resolve_night,
    resolve_vote_round,
    set_game_status,
)
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

logger = logging.getLogger(__name__)

# 防止同一局游戏重复启动 AI 循环
_cycle_locks: dict[str, asyncio.Lock] = {}


def _role_hint(role: RoleType) -> str:
    """使用角色技能注册表获取 AI 提示词"""
    return get_skill(role).ai_hint


_PHASE_HINT = {
    GameStatus.night: "夜晚阶段",
    GameStatus.day: "白天阶段",
    GameStatus.speak: "发言阶段（玩家轮流发言）",
    GameStatus.vote: "投票阶段",
    GameStatus.end: "游戏结束",
}


def _mock_speech(player_name: str, role: RoleType, round_no: int) -> str:
    """使用角色技能注册表获取 mock 发言"""
    return get_mock_speech(role, round_no)


def _mock_vote_target(game_id: str, player_id: str) -> str:
    candidates = [player for player in list_alive_players(game_id) if player.id != player_id]
    if not candidates:
        return player_id
    return candidates[0].id


def _effective_ai_config(game_id: str) -> AiRuntimeConfig:
    game = get_game_state(game_id)
    configured = game.room_settings.ai
    return AiRuntimeConfig(
        base_url=configured.base_url or settings.ai_api_base_url,
        api_key=configured.api_key or settings.ai_api_key,
        model=configured.model or settings.ai_model,
        timeout_seconds=configured.timeout_seconds or settings.ai_timeout_seconds,
        temperature=configured.temperature,
        enable_mock=configured.enable_mock,
    )


async def _call_openai_compatible(
    game_id: str,
    messages: list[dict[str, str]],
    response_format: dict[str, str] | None = None,
) -> str | None:
    runtime = _effective_ai_config(game_id)
    if runtime.enable_mock:
        logger.debug("[AI] game=%s mock模式开启，跳过API调用", game_id)
        return None
    if not runtime.base_url:
        logger.warning("[AI] game=%s base_url为空，无法调用API", game_id)
        return None
    if not runtime.api_key:
        logger.warning("[AI] game=%s api_key为空，无法调用API", game_id)
        return None

    try:
        return await _post_openai_compatible(runtime, messages, response_format)
    except Exception as exc:
        logger.error("[AI] game=%s API调用失败，回退到模拟: %s", game_id, exc)
        return None


async def _post_openai_compatible(
    runtime: AiRuntimeConfig,
    messages: list[dict[str, str]],
    response_format: dict[str, str] | None = None,
) -> str:
    # 清理 base_url 和 api_key 的前后空白（常见问题：复制粘贴带空格）
    base_url = runtime.base_url.strip()
    api_key = runtime.api_key.strip()

    if not base_url or not api_key:
        raise AppError("API Base URL 或 API Key 为空，无法调用", status_code=400)

    payload: dict[str, Any] = {
        "model": runtime.model.strip(),
        "messages": messages,
        "temperature": runtime.temperature,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    logger.info(
        "[AI] Calling API: url=%s model=%s temperature=%s",
        url, runtime.model.strip(), runtime.temperature,
    )

    async with httpx.AsyncClient(timeout=runtime.timeout_seconds) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
        )

        # ── 按状态码分类处理，尽可能展示服务端返回的具体错误 ──
        if response.status_code == 400:
            body = _safe_response_body(response)
            logger.error("[AI] 400 Bad Request from %s model=%s body=%s", url, runtime.model, body)
            raise AppError(
                f"请求参数错误（400）：API 拒绝了请求。"
                f"常见原因：①模型名称({runtime.model})不被该服务支持；"
                f"②请求参数格式不兼容（如 temperature/stream 等）；"
                f"③API Key 与该服务不匹配。\n"
                f"服务端返回：{body}",
                status_code=400,
            )
        if response.status_code == 401:
            logger.error("AI API 401 Unauthorized for %s — check API Key", url)
            raise AppError(
                f"认证失败（401）：API Key 无效或已过期。请检查 Key 是否正确，"
                f"以及是否对应 base_url（{base_url}）的访问权限。",
                status_code=401,
            )
        if response.status_code == 403:
            logger.error("AI API 403 Forbidden for %s", url)
            raise AppError(
                f"权限不足（403）：API Key 没有访问该模型的权限。"
                f"请检查模型名称（{runtime.model}）是否正确，以及 Key 是否有对应权限。",
                status_code=403,
            )
        if response.status_code == 404:
            logger.error("AI API 404 Not Found for %s model=%s", url, runtime.model)
            raise AppError(
                f"接口未找到（404）：请检查 base_url 是否正确。"
                f"火山引擎格式：https://ark.cn-beijing.volces.com/api/v3 ，"
                f"模型应填 endpoint ID（如 ep-xxx），不是 gpt-4o-mini。",
                status_code=404,
            )
        if response.status_code >= 400:
            body = _safe_response_body(response)
            logger.error("[AI] %s from %s model=%s body=%s", response.status_code, url, runtime.model, body)
            raise AppError(
                f"API 调用失败（{response.status_code}）：{body}",
                status_code=response.status_code,
            )

        data = response.json()

    return data["choices"][0]["message"]["content"]


def _safe_response_body(response: httpx.Response) -> str:
    """安全提取响应体文本，供错误信息展示"""
    try:
        return response.text[:500]
    except Exception:
        return "(无法读取响应体)"


async def test_ai_connection(game_id: str, runtime: AiRuntimeConfig | None = None) -> dict[str, object]:
    runtime = runtime or _effective_ai_config(game_id)
    if not runtime.base_url or not runtime.api_key:
        raise AppError("请先配置 API Base URL 和 API Key", status_code=400)

    messages = [
        {
            "role": "system",
            "content": "你是在做连接测试，只返回一个简短的中文确认词，不要解释。",
        },
        {
            "role": "user",
            "content": "请回复：连通成功",
        },
    ]

    try:
        content = await _post_openai_compatible(runtime, messages)
    except AppError:
        # 已经是友好错误信息（400/401/403/404等），直接透传
        raise
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.exception("AI connection test failed for game %s", game_id)
        raise AppError(f"AI 连通性测试失败：{exc}", status_code=502) from exc

    message = content.strip().strip('"') if content else "连通成功"
    return {
        "success": True,
        "message": message or "连通成功",
        "baseUrl": runtime.base_url,
        "model": runtime.model,
        "enableMock": runtime.enable_mock,
    }


async def _generate_ai_speech(game_id: str, player_id: str) -> str:
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return "我暂时没有发言。"

    # ── 更新压缩记忆 ──
    from app.services.memory_service import memory_manager, update_structured_memory_from_game
    store = memory_manager.get_or_create(game_id, player_id, player.name, player.role)
    update_structured_memory_from_game(store, game.players, game_id)

    # 把最近发言灌入滑动窗口
    for chat in game.chats[-8:]:
        store.record_speech(str(chat.get("playerName", "?")), str(chat.get("content", "")))

    # ── 构建游戏上下文（使用压缩记忆） ──
    phase_hint = _PHASE_HINT.get(game.game_status, "未知阶段")

    # 同阵营队友信息（使用注册表判断阵营）
    teammate_info = ""
    player_skill = get_skill(player.role)
    if player_skill.faction == "wolf":
        teammates = [
            p.name for p in game.players
            if SKILL_REGISTRY[p.role].faction == "wolf" and p.id != player_id and p.is_alive
        ]
        if teammates:
            teammate_info = f"\n你的狼人队友：{'、'.join(teammates)}（你们需要配合投票和击杀）"

    # 压缩后的上下文（替代原始发言记录）
    compressed_context = store.build_context(max_tokens=1500)

    messages = [
        {
            "role": "system",
            "content": (
                "你是在玩狼人杀的AI玩家。请用一句自然的中文发言，不要加引号，不要输出JSON，"
                "不要重复别人的话，不要暴露自己的AI身份。发言要像真人玩家一样有逻辑和情感。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"{_role_hint(player.role)}\n"
                f"当前阶段：{phase_hint}\n"
                f"当前轮次：第{game.current_round}轮\n"
                f"你的名字：{player.name}\n"
                f"{teammate_info}\n"
                f"{compressed_context}\n"
                "请给出你本轮的发言（只用说一句话，自然地参与讨论）。"
            ),
        },
    ]

    content = await _call_openai_compatible(game_id, messages)
    if content:
        logger.info("[AI] game=%s player=%s 使用真实API发言", game_id, player.name)
        return content.strip().strip('"')
    logger.info("[AI] game=%s player=%s 使用模拟发言", game_id, player.name)
    return _mock_speech(player.name, player.role, game.current_round)


async def _generate_ai_vote(game_id: str, player_id: str) -> str:
    """Generate AI vote. Candidate roles are masked as 'unknown' for non-self players
    to prevent role leakage in the prompt. Wolves can see their teammates."""
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return player_id

    candidates = []
    for item in game.players:
        if not item.is_alive or item.id == player_id:
            continue
        # 同阵营能看到队友身份，其他角色看到 unknown
        if SKILL_REGISTRY[player.role].faction == "wolf" and SKILL_REGISTRY[item.role].faction == "wolf":
            candidate_role = f"{get_skill(item.role).name}（你的队友）"
        else:
            candidate_role = "未知"
        candidates.append({
            "id": item.id,
            "name": item.name,
            "role": candidate_role,
            "isAlive": item.is_alive,
        })

    if not candidates:
        return player_id

    # ── 压缩记忆 ──
    from app.services.memory_service import memory_manager, update_structured_memory_from_game
    store = memory_manager.get_or_create(game_id, player_id, player.name, player.role)
    update_structured_memory_from_game(store, game.players, game.game_id)
    compressed_context = store.build_context(max_tokens=800)

    # 构建投票提示（使用注册表判断阵营）
    teammate_vote_hint = ""
    if SKILL_REGISTRY[player.role].faction == "wolf":
        teammates = [
            p.name for p in game.players
            if SKILL_REGISTRY[p.role].faction == "wolf" and p.id != player_id and p.is_alive
        ]
        if teammates:
            teammate_vote_hint = f"\n你的狼人队友：{'、'.join(teammates)}，你们应协调投票，不要投队友。"

    messages = [
        {
            "role": "system",
            "content": "你是在玩狼人杀的AI玩家，现在处于投票阶段。只输出一个要投票的玩家ID，不要解释，不要输出JSON。",
        },
        {
            "role": "user",
            "content": (
                f"你的身份：{_role_hint(player.role)}\n"
                f"当前轮次：第{game.current_round}轮\n"
                f"候选名单：{json.dumps(candidates, ensure_ascii=False)}\n"
                f"{teammate_vote_hint}\n"
                f"{compressed_context}\n"
                "请直接返回你要投票的玩家ID。"
            ),
        },
    ]

    content = await _call_openai_compatible(game_id, messages)
    if content:
        target_id = content.strip().strip('"')
        if any(candidate["id"] == target_id for candidate in candidates):
            logger.info("[AI] game=%s player=%s 使用真实API投票→%s", game_id, player.name, target_id)
            return target_id
        logger.warning("[AI] game=%s player=%s API返回无效投票ID=%s，回退模拟", game_id, player.name, target_id)
    logger.info("[AI] game=%s player=%s 使用模拟投票", game_id, player.name)
    return _mock_vote_target(game_id, player_id)


async def _generate_ai_night_action(game_id: str, player_id: str) -> str:
    """Generate AI night action target using RoleSkill registry.
    - Uses skill.night_action_type to determine behavior
    - Uses skill.faction to determine valid targets
    Returns target_id or empty string.
    """
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return ""

    skill = get_skill(player.role)
    if not skill.has_night_action:
        return ""

    # 构建目标列表
    if skill.faction == "wolf":
        # 狼人：选非狼人存活玩家
        targets = [p for p in game.players if p.is_alive and SKILL_REGISTRY[p.role].faction != "wolf" and p.id != player_id]
    else:
        # 好人阵营：选存活非己玩家
        targets = [p for p in game.players if p.is_alive and p.id != player_id]

    # 守卫不能连续守同一人
    if not skill.consecutive_target_allowed and player.last_guard_target_id:
        filtered = [p for p in targets if p.id != player.last_guard_target_id]
        if filtered:
            targets = filtered

    if not targets:
        return ""
    return random.choice(targets).id


async def run_ai_cycle(game_id: str) -> None:
    """Full game cycle: night → day → speak → vote, repeating until game over."""
    game = get_game_state(game_id)
    if game.ai_cycle_running or game.winner_faction is not None:
        return

    game.ai_cycle_running = True
    try:
        max_rounds = 10
        while game.current_round <= max_rounds:
            game = get_game_state(game_id)
            if game.winner_faction is not None:
                break

            # === Night Phase ===
            set_game_status(game_id, GameStatus.night)
            game = get_game_state(game_id)
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.night.value, "currentRound": game.current_round},
                ).model_dump_json(),
            )

            # AI wolves act
            alive_ai_wolves = [
                p for p in game.players
                if p.is_ai and p.is_alive and p.role == RoleType.wolf
            ]
            for ai_wolf in alive_ai_wolves:
                target = await _generate_ai_night_action(game_id, ai_wolf.id)
                if target:
                    record_night_action(game_id, ai_wolf.id, target)

            # AI prophets act
            alive_ai_prophets = [
                p for p in game.players
                if p.is_ai and p.is_alive and p.role == RoleType.prophet
            ]
            for ai_prophet in alive_ai_prophets:
                target = await _generate_ai_night_action(game_id, ai_prophet.id)
                if target:
                    record_night_action(game_id, ai_prophet.id, target)

            # AI guards act
            alive_ai_guards = [
                p for p in game.players
                if p.is_ai and p.is_alive and p.role == RoleType.guard
            ]
            for ai_guard in alive_ai_guards:
                target = await _generate_ai_night_action(game_id, ai_guard.id)
                if target:
                    record_night_action(game_id, ai_guard.id, target)

            # Notify human players to act
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.night_action,
                    timestamp=utc_now_iso(),
                    payload={"actionRequired": True},
                ).model_dump_json(),
            )

            # Wait for human night actions
            game = get_game_state(game_id)
            speak_timeout = game.room_settings.scene.speak_timeout_seconds
            await asyncio.sleep(speak_timeout)

            # Resolve night
            night_result = resolve_night(game_id)

            # Broadcast night result
            killed_id = night_result.get("killed_player_id")
            checked_results = night_result.get("checked_results", [])

            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.night_result,
                    timestamp=utc_now_iso(),
                    payload={
                        "killedPlayerId": killed_id,
                        "guardedPlayerId": night_result.get("guarded_player_id"),
                        "guardBlocked": night_result.get("guard_blocked", False),
                        "checkedResults": checked_results,
                    },
                ).model_dump_json(),
            )

            # Broadcast player update for killed player
            if killed_id:
                killed_player = next(
                    (p for p in get_game_state(game_id).players if p.id == killed_id), None
                )
                # Note: the player is already marked dead in resolve_night,
                # but we still have their name in the game state
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.player_update,
                        timestamp=utc_now_iso(),
                        payload={
                            "playerId": killed_id,
                            "isAlive": False,
                            "playerName": killed_player.name if killed_player else "",
                        },
                    ).model_dump_json(),
                )

            # Check win condition after night
            game = get_game_state(game_id)
            if game.winner_faction is not None:
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.game_over,
                        timestamp=utc_now_iso(),
                        payload={
                            "gameId": game_id,
                            "winnerFaction": game.winner_faction,
                            "currentRound": game.current_round,
                            "players": [p.model_dump(by_alias=True) for p in game.players],
                            "chats": game.chats,
                            "announcements": game.announcements,
                        },
                    ).model_dump_json(),
                )
                break

            # === Day Phase ===
            set_game_status(game_id, GameStatus.day)
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.day.value},
                ).model_dump_json(),
            )
            await asyncio.sleep(2)  # Day announcement pause

            # === Speak Phase ===
            set_game_status(game_id, GameStatus.speak)
            current_speaker_id = begin_speak_turn(game_id)
            speak_turn_ids = get_game_state(game_id).speak_order or [player.id for player in get_game_state(game_id).players if player.is_alive]
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={
                        "status": GameStatus.speak.value,
                        "currentRound": get_game_state(game_id).current_round,
                        "currentSpeakerId": current_speaker_id,
                    },
                ).model_dump_json(),
            )
            for turn_index, speaker_id in enumerate(speak_turn_ids):
                game = get_game_state(game_id)
                if game.winner_faction is not None:
                    break

                game.current_speaker_id = speaker_id
                game.speak_turn_submitted = False
                speaker = next((player for player in game.players if player.id == speaker_id), None)

                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.speak_turn,
                        timestamp=utc_now_iso(),
                        payload={
                            "currentSpeakerId": speaker_id,
                            "currentSpeakerName": speaker.name if speaker else "",
                            "turnIndex": turn_index + 1,
                            "turnCount": len(speak_turn_ids),
                        },
                    ).model_dump_json(),
                )
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.announce,
                        timestamp=utc_now_iso(),
                        payload={"content": f"轮到 {speaker.name if speaker else '玩家'} 发言"},
                    ).model_dump_json(),
                )

                if speaker and speaker.is_ai:
                    speech = await _generate_ai_speech(game_id, speaker.id)
                    record_speak(game_id, speaker.id, speech)
                    await manager.broadcast(
                        game_id,
                        SocketMessage(
                            type=MessageType.ai_speak,
                            timestamp=utc_now_iso(),
                            payload={
                                "content": speech,
                                "playerId": speaker.id,
                                "playerName": speaker.name,
                                "isAI": True,
                            },
                        ).model_dump_json(),
                    )
                    await asyncio.sleep(0.2)
                else:
                    game_ref = get_game_state(game_id)
                    speak_timeout = game_ref.room_settings.scene.speak_timeout_seconds
                    deadline = asyncio.get_running_loop().time() + speak_timeout
                    while asyncio.get_running_loop().time() < deadline:
                        current_game = get_game_state(game_id)
                        if current_game.speak_turn_submitted:
                            break
                        await asyncio.sleep(0.25)

                advance_speak_turn(game_id)

            # === Vote Phase ===
            set_game_status(game_id, GameStatus.vote)
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.vote.value, "currentRound": get_game_state(game_id).current_round},
                ).model_dump_json(),
            )

            # AI players vote
            for ai_player in list_ai_players(game_id):
                target_id = await _generate_ai_vote(game_id, ai_player.id)
                record_vote(game_id, ai_player.id, target_id)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.vote_result,
                        timestamp=utc_now_iso(),
                        payload={"voterId": ai_player.id, "targetId": target_id},
                    ).model_dump_json(),
                )
                await asyncio.sleep(0.2)

            # Wait for human votes
            await asyncio.sleep(settings.ai_vote_window_seconds)

            # Resolve vote
            result = resolve_vote_round(game_id)
            if result["eliminated"]:
                eliminated = next(
                    (item for item in get_game_state(game_id).players if item.id == result["eliminated"]),
                    None,
                )
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.player_update,
                        timestamp=utc_now_iso(),
                        payload={
                            "playerId": result["eliminated"],
                            "isAlive": False,
                            "playerName": eliminated.name if eliminated else "",
                        },
                    ).model_dump_json(),
                )

            if result.get("winnerFaction"):
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.game_over,
                        timestamp=utc_now_iso(),
                        payload={
                            "gameId": game_id,
                            "winnerFaction": result["winnerFaction"],
                            "currentRound": result["currentRound"],
                            "players": [p.model_dump(by_alias=True) for p in get_game_state(game_id).players],
                            "chats": get_game_state(game_id).chats,
                            "announcements": get_game_state(game_id).announcements,
                        },
                    ).model_dump_json(),
                )
                break

            clear_votes(game_id)
            await asyncio.sleep(0.75)

    except (AppError, httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError):
        logger.exception("AI cycle failed for game %s", game_id)
    finally:
        game = get_game_state(game_id)
        game.ai_cycle_running = False


def launch_ai_cycle(game_id: str) -> None:
    """启动 AI 游戏循环 — 委托给法官类"""
    from app.services.judge_service import Judge

    if game_id not in _cycle_locks:
        _cycle_locks[game_id] = asyncio.Lock()

    async def _guarded_launch() -> None:
        lock = _cycle_locks[game_id]
        if lock.locked():
            return
        async with lock:
            game = get_game_state(game_id)
            if game.ai_cycle_running or game.winner_faction is not None:
                return
            judge = Judge(game_id)
            await judge.run_game()

    asyncio.create_task(_guarded_launch())
