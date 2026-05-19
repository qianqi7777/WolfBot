import asyncio
import json
import logging
import random
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.enums import GameStatus, MessageType, RoleType
from app.schemas.socket import SocketMessage
from app.services.game_service import (
    AiRuntimeConfig,
    clear_votes,
    get_game_state,
    get_player_role,
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


def _role_hint(role: RoleType) -> str:
    return {
        RoleType.wolf: "你是狼人，要伪装自己，发言简短自然。",
        RoleType.prophet: "你是预言家，要谨慎表达，不要暴露过多细节。",
        RoleType.guard: "你是守卫，要尽量保护关键目标，发言时避免暴露身份。",
        RoleType.civilian: "你是平民，要根据已知信息分析局势。",
        RoleType.unknown: "你的身份未知，按正常玩家语气发言。",
    }[role]


def _mock_speech(player_name: str, role: RoleType, round_no: int) -> str:
    base = {
        RoleType.wolf: "我先观察一下大家的发言，暂时不下结论。",
        RoleType.prophet: "我这轮先记录信息，后面再给出判断。",
        RoleType.civilian: "我目前还在整理线索，先跟大家讨论。",
        RoleType.unknown: "我先听听大家的意见，再做判断。",
    }[role]
    return f"{player_name}：{base}（第{round_no}轮）"


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
    if runtime.enable_mock or not runtime.base_url or not runtime.api_key:
        return None

    payload: dict[str, Any] = {
        "model": runtime.model,
        "messages": messages,
        "temperature": runtime.temperature,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {runtime.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=runtime.timeout_seconds) as client:
        response = await client.post(
            f"{runtime.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"]


async def _generate_ai_speech(game_id: str, player_id: str) -> str:
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return "我暂时没有发言。"

    messages = [
        {
            "role": "system",
            "content": "你是狼人杀对局中的AI玩家，只输出一句中文发言，不要加引号，不要输出JSON。",
        },
        {
            "role": "user",
            "content": (
                f"{_role_hint(player.role)}\n"
                f"当前轮次: {game.current_round}\n"
                f"当前阶段: {game.game_status.value}\n"
                f"存活玩家: {', '.join(item.name for item in game.players if item.is_alive)}\n"
                f"你的名字: {player.name}\n"
                "请给出一句自然的游戏发言。"
            ),
        },
    ]

    content = await _call_openai_compatible(game_id, messages)
    if content:
        return content.strip().strip('"')
    return _mock_speech(player.name, player.role, game.current_round)


async def _generate_ai_vote(game_id: str, player_id: str) -> str:
    """Generate AI vote. Candidate roles are masked as 'unknown' for non-self players
    to prevent role leakage in the prompt."""
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return player_id

    candidates = [
        {
            "id": item.id,
            "name": item.name,
            "role": item.role.value if item.id == player_id else RoleType.unknown.value,
            "isAlive": item.is_alive,
        }
        for item in game.players
        if item.is_alive and item.id != player_id
    ]
    if not candidates:
        return player_id

    messages = [
        {
            "role": "system",
            "content": "你是狼人杀对局中的AI玩家，只输出一个要投票的玩家ID，不要解释，不要输出JSON。",
        },
        {
            "role": "user",
            "content": (
                f"你的身份: {player.role.value}\n"
                f"当前轮次: {game.current_round}\n"
                f"候选名单: {json.dumps(candidates, ensure_ascii=False)}\n"
                "请直接返回你要投票的玩家ID。"
            ),
        },
    ]

    content = await _call_openai_compatible(game_id, messages)
    if content:
        target_id = content.strip().strip('"')
        if any(candidate["id"] == target_id for candidate in candidates):
            return target_id
    return _mock_vote_target(game_id, player_id)


async def _generate_ai_night_action(game_id: str, player_id: str) -> str:
    """Generate AI night action target.
    - Wolf: randomly pick an alive non-wolf player to kill.
    - Prophet: randomly pick an alive non-self player to check.
    - Guard: randomly pick an alive non-self player to protect.
    Returns target_id.
    """
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return ""

    if player.role == RoleType.wolf:
        targets = [p for p in game.players if p.is_alive and p.role != RoleType.wolf and p.id != player_id]
    elif player.role == RoleType.prophet:
        targets = [p for p in game.players if p.is_alive and p.id != player_id]
    elif player.role == RoleType.guard:
        targets = [p for p in game.players if p.is_alive and p.id != player_id]
        if player.last_guard_target_id:
            filtered = [p for p in targets if p.id != player.last_guard_target_id]
            if filtered:
                targets = filtered
    else:
        # Other roles have no night action; return empty
        return ""

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
            await asyncio.sleep(settings.ai_speak_window_seconds)

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
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.speak.value, "currentRound": get_game_state(game_id).current_round},
                ).model_dump_json(),
            )

            # AI players speak
            for ai_player in list_ai_players(game_id):
                speech = await _generate_ai_speech(game_id, ai_player.id)
                record_speak(game_id, ai_player.id, speech)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.ai_speak,
                        timestamp=utc_now_iso(),
                        payload={
                            "content": speech,
                            "playerId": ai_player.id,
                            "playerName": ai_player.name,
                            "isAI": True,
                        },
                    ).model_dump_json(),
                )
                await asyncio.sleep(0.3)

            # Wait for human speech
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.announce,
                    timestamp=utc_now_iso(),
                    payload={"content": "请在规定时间内发言"},
                ).model_dump_json(),
            )
            await asyncio.sleep(settings.ai_speak_window_seconds)

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
    asyncio.create_task(run_ai_cycle(game_id))
