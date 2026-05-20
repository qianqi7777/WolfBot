import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AppError
from app.domain.enums import MessageType
from app.schemas.socket import SocketMessage
from app.services.game_service import change_seat, get_game, get_game_state, get_player_role, record_night_action, record_speak, record_last_words, record_vote, start_game, record_role_selection
from app.domain.enums import GameStatus, RoleType
from app.domain.roles import SKILL_REGISTRY
from app.services.ai_service import launch_ai_cycle
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

router = APIRouter()


@router.websocket("/ws/game")
async def game_ws(websocket: WebSocket) -> None:
    game_id = websocket.query_params.get("gameId", "")
    player_id = websocket.query_params.get("playerId", "")
    await manager.connect(game_id, websocket, player_id=player_id)
    try:
        snapshot = get_game(game_id, requester_id=player_id or None)
        await manager.send_to(
            websocket,
            SocketMessage(
                type=MessageType.room_update,
                timestamp=utc_now_iso(),
                payload={
                    "gameId": snapshot.game_id,
                    "players": [player.model_dump(by_alias=True) for player in snapshot.players],
                    "currentSpeakerId": snapshot.current_speaker_id,
                    "roomSettings": snapshot.room_settings.model_dump(by_alias=True),
                    "ownerPlayerId": snapshot.owner_player_id,
                },
            ).model_dump_json(),
        )
        await manager.send_to(
            websocket,
            SocketMessage(
                type=MessageType.game_status,
                timestamp=utc_now_iso(),
                payload={
                    "status": snapshot.game_status.value,
                    "currentRound": snapshot.current_round,
                    "currentSpeakerId": snapshot.current_speaker_id,
                },
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
                    actor_id = player_id or snapshot.player_id
                    record_speak(game_id, actor_id, content)
                    # 使用最新的玩家数据获取座位号
                    game = get_game_state(game_id)
                    speaker = next((p for p in game.players if p.id == actor_id), None)
                    display_name = f"{speaker.seat_number}号({speaker.name})" if speaker else "玩家"
                    await manager.broadcast(
                        game_id,
                        SocketMessage(
                            type=MessageType.player_speak,
                            timestamp=utc_now_iso(),
                            payload={
                                "content": content,
                                "playerId": actor_id,
                                "playerName": display_name,
                                "isAI": speaker.is_ai if speaker else False,
                            },
                        ).model_dump_json(),
                    )
            elif message_type == "last_words":
                # 遗言消息：允许死亡玩家发言
                content = str(payload.get("content", "")).strip()
                if content:
                    actor_id = player_id or snapshot.player_id
                    try:
                        record_last_words(game_id, actor_id, content)
                        game = get_game_state(game_id)
                        speaker = next((p for p in game.players if p.id == actor_id), None)
                        display_name = f"{speaker.seat_number}号({speaker.name})【遗言】" if speaker else "玩家"
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.player_speak,
                                timestamp=utc_now_iso(),
                                payload={
                                    "content": content,
                                    "playerId": actor_id,
                                    "playerName": display_name,
                                    "isAI": speaker.is_ai if speaker else False,
                                },
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "vote":
                target_id = str(payload.get("targetId", "")).strip()
                # 支持弃票：targetId 为空或 "abstain"
                effective_target = target_id if target_id and target_id != "abstain" else "abstain"
                record_vote(game_id, player_id or snapshot.player_id, effective_target)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.vote_result,
                        timestamp=utc_now_iso(),
                        payload={"targetId": effective_target, "voterId": player_id or snapshot.player_id},
                    ).model_dump_json(),
                )
            elif message_type == "night_action":
                target_id = str(payload.get("targetId", "")).strip()
                if target_id and (player_id or snapshot.player_id):
                    try:
                        actor_id = player_id or snapshot.player_id
                        record_night_action(game_id, actor_id, target_id)
                        await manager.send_to(
                            websocket,
                            SocketMessage(
                                type=MessageType.announce,
                                timestamp=utc_now_iso(),
                                payload={"content": "夜间行动已提交"},
                            ).model_dump_json(),
                        )
                        # 狼人刀目标实时通知队友
                        game = get_game_state(game_id)
                        actor = next((p for p in game.players if p.id == actor_id), None)
                        if actor and actor.role == RoleType.wolf:
                            target_player = next((p for p in game.players if p.id == target_id), None)
                            target_label = f"{target_player.seat_number}号" if target_player else "未知"
                            actor_label = f"{actor.seat_number}号"
                            # 向其他存活狼人私发
                            for p in game.players:
                                if p.id != actor_id and p.is_alive and SKILL_REGISTRY[p.role].faction == "wolf":
                                    await manager.send_to_player(
                                        game_id, p.id,
                                        SocketMessage(
                                            type=MessageType.wolf_target_update,
                                            timestamp=utc_now_iso(),
                                            payload={
                                                "wolfId": actor_id,
                                                "wolfSeat": actor.seat_number,
                                                "targetId": target_id,
                                                "targetSeat": target_player.seat_number if target_player else 0,
                                                "message": f"{actor_label}选择了{target_label}为击杀目标",
                                            },
                                        ).model_dump_json(),
                                    )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "change_seat":
                seat_number = int(payload.get("seatNumber", 0))
                if seat_number > 0 and player_id:
                    try:
                        cs_snapshot = change_seat(game_id, player_id, seat_number)
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.room_update,
                                timestamp=utc_now_iso(),
                                payload={
                                    "gameId": game_id,
                                    "players": [p.model_dump(by_alias=True) for p in cs_snapshot.players],
                                },
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "ping":
                await manager.send_to(
                    websocket,
                    SocketMessage(type=MessageType.announce, timestamp=utc_now_iso(), payload={"content": "pong"}).model_dump_json(),
                )
            elif message_type == "start":
                # 房主校验
                game = get_game_state(game_id)
                if game.owner_player_id and player_id != game.owner_player_id:
                    await manager.send_to(
                        websocket,
                        SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": "只有房主可以开始游戏"}).model_dump_json(),
                    )
                    continue
                started_snapshot = start_game(game_id, requester_id=player_id or None)
                launch_ai_cycle(game_id)
                await manager.broadcast(
                    game_id,
                    SocketMessage(
                        type=MessageType.game_status,
                        timestamp=utc_now_iso(),
                        payload={
                            "status": started_snapshot.game_status.value,
                            "currentRound": started_snapshot.current_round,
                            "currentSpeakerId": started_snapshot.current_speaker_id,
                            "gameMode": started_snapshot.game_mode,
                        },
                    ).model_dump_json(),
                )
                # 抢身份模式下不立即发送角色信息，等抢身份阶段结束后由 Judge 发送
                if started_snapshot.game_status != GameStatus.role_select and player_id:
                    try:
                        await manager.send_to(
                            websocket,
                            SocketMessage(
                                type=MessageType.role_info,
                                timestamp=utc_now_iso(),
                                payload={"role": get_player_role(game_id, player_id).value},
                            ).model_dump_json(),
                        )
                    except AppError:
                        pass
            elif message_type == "role_select_choice":
                # 抢身份选择
                chosen_role = str(payload.get("role", "")).strip()
                if chosen_role and player_id:
                    try:
                        record_role_selection(game_id, player_id, chosen_role)
                        await manager.send_to(
                            websocket,
                            SocketMessage(
                                type=MessageType.announce,
                                timestamp=utc_now_iso(),
                                payload={"content": f"已选择身份，等待抢身份阶段结束"},
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
    except AppError as exc:
        await manager.send_to(
            websocket,
            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
        )
