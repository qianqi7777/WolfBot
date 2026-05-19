import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AppError
from app.domain.enums import MessageType
from app.schemas.socket import SocketMessage
from app.services.game_service import get_game, get_player_role, record_speak, record_vote, start_game
from app.services.ai_service import launch_ai_cycle
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

router = APIRouter()


@router.websocket("/ws/game")
async def game_ws(websocket: WebSocket) -> None:
    game_id = websocket.query_params.get("gameId", "")
    player_id = websocket.query_params.get("playerId", "")
    await manager.connect(game_id, websocket)
    try:
        snapshot = get_game(game_id)
        await manager.send_to(
            websocket,
            SocketMessage(
                type=MessageType.room_update,
                timestamp=utc_now_iso(),
                payload={"gameId": snapshot.game_id, "players": [player.model_dump(by_alias=True) for player in snapshot.players]},
            ).model_dump_json(),
        )
        await manager.send_to(
            websocket,
            SocketMessage(
                type=MessageType.game_status,
                timestamp=utc_now_iso(),
                payload={"status": snapshot.game_status.value, "currentRound": snapshot.current_round},
            ).model_dump_json(),
        )
        if player_id:
            try:
                role = get_player_role(game_id, player_id)
                await manager.send_to(
                    websocket,
                    SocketMessage(
                        type=MessageType.role_info,
                        timestamp=utc_now_iso(),
                        payload={"role": role.value},
                    ).model_dump_json(),
                )
            except AppError:
                pass
        await manager.send_to(
            websocket,
            SocketMessage(type=MessageType.announce, timestamp=utc_now_iso(), payload={"content": f"进入房间 {snapshot.game_id}"}).model_dump_json(),
        )
        while True:
            raw_message = await websocket.receive_text()
            try:
                parsed = json.loads(raw_message)
            except json.JSONDecodeError:
                await manager.send_to(
                    websocket,
                    SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": "无效消息"}).model_dump_json(),
                )
                continue
            if not isinstance(parsed, dict):
                await manager.send_to(
                    websocket,
                    SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": "消息格式错误"}).model_dump_json(),
                )
                continue

            message_type = parsed.get("type")
            payload = parsed.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            if message_type == "speak":
                content = str(payload.get("content", "")).strip()
                if content:
                    record_speak(game_id, player_id or snapshot.player_id, content)
                    speaker = next((item for item in snapshot.players if item.id == (player_id or snapshot.player_id)), None)
                    await manager.broadcast(
                        game_id,
                        SocketMessage(
                            type=MessageType.player_speak,
                            timestamp=utc_now_iso(),
                            payload={
                                "content": content,
                                "playerId": player_id or snapshot.player_id,
                                "playerName": speaker.name if speaker else "玩家",
                                "isAI": speaker.is_ai if speaker else False,
                            },
                        ).model_dump_json(),
                    )
            elif message_type == "vote":
                target_id = str(payload.get("targetId", "")).strip()
                if target_id:
                    record_vote(game_id, player_id or snapshot.player_id, target_id)
                    await manager.broadcast(
                        game_id,
                        SocketMessage(
                            type=MessageType.vote_result,
                            timestamp=utc_now_iso(),
                            payload={"targetId": target_id, "voterId": player_id or snapshot.player_id},
                        ).model_dump_json(),
                    )
            elif message_type == "ping":
                await manager.send_to(
                    websocket,
                    SocketMessage(type=MessageType.announce, timestamp=utc_now_iso(), payload={"content": "pong"}).model_dump_json(),
                )
            elif message_type == "start":
                started_snapshot = start_game(game_id)
                launch_ai_cycle(game_id)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.game_status,
                        timestamp=utc_now_iso(),
                        payload={"status": started_snapshot.game_status.value, "currentRound": started_snapshot.current_round},
                    ).model_dump_json(),
                )
                if player_id:
                    await manager.send_to(
                        websocket,
                        SocketMessage(
                            type=MessageType.role_info,
                            timestamp=utc_now_iso(),
                            payload={"role": get_player_role(game_id, player_id).value},
                        ).model_dump_json(),
                    )
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
    except AppError as exc:
        await manager.send_to(
            websocket,
            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
        )
