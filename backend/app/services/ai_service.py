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
    get_game_state,
    get_seat_map,
    list_ai_players,
    list_alive_players,
    record_night_action,
)
from app.utils.time import utc_now_iso

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

    # 把最近发言灌入滑动窗口（用座位号标识发言人）
    seat_map = get_seat_map(game_id)
    for chat in game.chats[-8:]:
        speaker_id = str(chat.get("playerId", ""))
        seat = seat_map.get(speaker_id)
        speaker_label = f"{seat}号" if seat else str(chat.get("playerName", "?"))
        store.record_speech(speaker_label, str(chat.get("content", "")))

    # ── 构建游戏上下文（使用压缩记忆） ──
    phase_hint = _PHASE_HINT.get(game.game_status, "未知阶段")

    # 座位号映射
    seat_map = get_seat_map(game_id)
    my_seat = player.seat_number

    # 同阵营队友信息（使用座位号标识）
    teammate_info = ""
    player_skill = get_skill(player.role)
    if player_skill.faction == "wolf":
        teammates = [
            f"{p.seat_number}号" for p in game.players
            if SKILL_REGISTRY[p.role].faction == "wolf" and p.id != player_id and p.is_alive
        ]
        if teammates:
            teammate_info = f"\n你的狼人队友：{'、'.join(teammates)}（你们需要配合投票和击杀）"

    # ── 存活玩家名单（用座位号） ──
    alive_list = []
    for p in game.players:
        if p.is_alive and p.id != player_id:
            alive_list.append(f"{p.seat_number}号")
    alive_info = f"\n其他存活玩家：{'、'.join(alive_list)}" if alive_list else ""

    # 压缩后的上下文（替代原始发言记录）
    compressed_context = store.build_context(max_tokens=1500)

    messages = [
        {
            "role": "system",
            "content": (
                "你是在玩狼人杀的AI玩家。请用一句自然的中文发言，不要加引号，不要输出JSON，"
                "不要重复别人的话，不要暴露自己的AI身份。发言要像真人玩家一样有逻辑和情感。"
                "提到其他玩家时请用'X号'（如'3号玩家'、'5号'），不要使用内部ID或编号。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"{_role_hint(player.role)}\n"
                f"当前阶段：{phase_hint}\n"
                f"当前轮次：第{game.current_round}轮\n"
                f"你是{my_seat}号玩家\n"
                f"{teammate_info}"
                f"{alive_info}\n"
                f"{compressed_context}\n"
                "请给出你本轮的发言（只用说一句话，自然地参与讨论，提到别人用X号）。"
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
            "seatNumber": item.seat_number,
            "name": f"{item.seat_number}号玩家",
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
            f"{p.seat_number}号" for p in game.players
            if SKILL_REGISTRY[p.role].faction == "wolf" and p.id != player_id and p.is_alive
        ]
        if teammates:
            teammate_vote_hint = f"\n你的狼人队友：{'、'.join(teammates)}，你们应协调投票，不要投队友。"

    messages = [
        {
            "role": "system",
            "content": (
                "你是在玩狼人杀的AI玩家，现在处于投票阶段。"
                "只输出一个你要投票的玩家座位号（数字），不要解释，不要输出JSON，不要加'号'字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"你的身份：{_role_hint(player.role)}\n"
                f"你是{player.seat_number}号玩家\n"
                f"当前轮次：第{game.current_round}轮\n"
                f"候选名单：{json.dumps(candidates, ensure_ascii=False)}\n"
                f"{teammate_vote_hint}\n"
                f"{compressed_context}\n"
                "请直接返回你要投票的玩家座位号（纯数字，如3）。"
            ),
        },
    ]

    content = await _call_openai_compatible(game_id, messages)
    if content:
        raw = content.strip().strip('"')
        import re
        m = re.search(r'\d+', raw)
        if m:
            target_seat = int(m.group())
            target_player = next(
                (p for p in game.players if p.seat_number == target_seat and p.is_alive and p.id != player_id),
                None,
            )
            if target_player:
                logger.info("[AI] game=%s player=%s号 使用真实API投票→%s号", game_id, player.seat_number, target_seat)
                return target_player.id
        logger.warning("[AI] game=%s player=%s号 API返回无效投票'%s'，回退模拟", game_id, player.seat_number, raw)
    logger.info("[AI] game=%s player=%s 使用模拟投票", game_id, player.name)
    return _mock_vote_target(game_id, player_id)


async def _generate_ai_night_action(game_id: str, player_id: str) -> tuple[str, str]:
    """Generate AI night action target using RoleSkill registry.
    - Uses skill.night_action_type to determine behavior
    - Uses skill.faction to determine valid targets
    Returns (target_id, action_type). action_type is non-empty only for witch (\"save\"/\"poison\").
    """
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return "", ""

    skill = get_skill(player.role)
    if not skill.has_night_action:
        return "", ""

    # 女巫特殊处理：选择使用解药或毒药
    if player.role == RoleType.witch:
        return _ai_witch_night_action(game, player)

    # 构建目标列表
    if skill.faction == "wolf":
        targets = [p for p in game.players if p.is_alive and (SKILL_REGISTRY[p.role].faction != "wolf" or p.id == player_id)]
    else:
        targets = [p for p in game.players if p.is_alive and p.id != player_id]

    # 守卫不能连续守同一人
    if not skill.consecutive_target_allowed and player.last_guard_target_id:
        filtered = [p for p in targets if p.id != player.last_guard_target_id]
        if filtered:
            targets = filtered

    if not targets:
        return "", ""
    return random.choice(targets).id, ""


def _ai_witch_night_action(game, player) -> tuple[str, str]:
    """AI 女巫夜间行动决策：优先用毒药杀狼人，解药救好人。"""
    alive_others = [p for p in game.players if p.is_alive and p.id != player.id]

    # 毒药未使用：毒杀疑似狼人（优先非平民）
    if not player.poison_used:
        # 优先毒杀已知狼人（根据之前的查验信息等，但AI没有记忆；简化为随机选择）
        # 策略：随机选择一个非自己的存活玩家
        if alive_others:
            target = random.choice(alive_others)
            # 有一定概率选择使用毒药
            if random.random() < 0.5:  # 50%概率使用毒药
                return target.id, "poison"

    # 解药未使用：救活一个随机的存活玩家（通常是好人）
    if not player.antidote_used:
        if alive_others:
            # 救一个非狼人阵营的玩家（AI女巫不知道谁被杀了，简化处理）
            target = random.choice(alive_others)
            if random.random() < 0.7:  # 70%概率使用解药
                return target.id, "save"

    # 都不使用或无法使用
    return "", ""


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
