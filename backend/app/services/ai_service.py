import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.domain.enums import GameStatus, MessageType, RoleType
from app.schemas.socket import SocketMessage
from app.services.game_service import (
    clear_votes,
    get_game_state,
    list_ai_players,
    list_alive_players,
    record_speak,
    record_vote,
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


async def _call_openai_compatible(messages: list[dict[str, str]], response_format: dict[str, str] | None = None) -> str | None:
    if settings.ai_enable_mock or not settings.ai_api_base_url or not settings.ai_api_key:
        return None

    payload: dict[str, Any] = {
        "model": settings.ai_model,
        "messages": messages,
        "temperature": settings.ai_temperature,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(
            f"{settings.ai_api_base_url.rstrip('/')}/chat/completions",
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

    content = await _call_openai_compatible(messages)
    if content:
        return content.strip().strip('"')
    return _mock_speech(player.name, player.role, game.current_round)


async def _generate_ai_vote(game_id: str, player_id: str) -> str:
    game = get_game_state(game_id)
    player = next((item for item in game.players if item.id == player_id), None)
    if player is None:
        return player_id

    candidates = [
        {"id": item.id, "name": item.name, "role": item.role.value, "isAlive": item.is_alive}
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

    content = await _call_openai_compatible(messages)
    if content:
        target_id = content.strip().strip('"')
        if any(candidate["id"] == target_id for candidate in candidates):
            return target_id
    return _mock_vote_target(game_id, player_id)


async def run_ai_cycle(game_id: str) -> None:
    game = get_game_state(game_id)
    if game.ai_cycle_running or game.winner_faction is not None:
        return

    game.ai_cycle_running = True
    try:
        max_rounds = 10
        for _ in range(max_rounds):
            game = get_game_state(game_id)
            if game.winner_faction is not None:
                break

            set_game_status(game_id, GameStatus.speak)
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.speak.value, "currentRound": game.current_round},
                ).model_dump_json(),
            )

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

            await asyncio.sleep(0.5)

            set_game_status(game_id, GameStatus.vote)
            await manager.broadcast(
                game_id,
                SocketMessage(
                    type=MessageType.game_status,
                    timestamp=utc_now_iso(),
                    payload={"status": GameStatus.vote.value, "currentRound": get_game_state(game_id).current_round},
                ).model_dump_json(),
            )

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

            await asyncio.sleep(settings.ai_vote_window_seconds)
            result = resolve_vote_round(game_id)
            if result["eliminated"]:
                eliminated = next((item for item in get_game_state(game_id).players if item.id == result["eliminated"]), None)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.player_update,
                        timestamp=utc_now_iso(),
                        payload={"playerId": result["eliminated"], "isAlive": False, "playerName": eliminated.name if eliminated else ""},
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
                            "players": [player.model_dump(by_alias=True) for player in get_game_state(game_id).players],
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
