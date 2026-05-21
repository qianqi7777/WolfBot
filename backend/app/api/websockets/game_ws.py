import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AppError
from app.domain.enums import MessageType
from app.schemas.socket import SocketMessage
from app.services.game_service import change_seat, get_game, get_game_state, get_player_role, record_night_action, record_speak, record_last_words, record_vote, start_game, record_role_selection, register_sheriff_campaign, withdraw_sheriff_campaign, record_sheriff_vote, transfer_sheriff_badge, wolf_self_destruct, _check_win_condition
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
                action_type = str(payload.get("actionType", "")).strip()  # 女巫用: "save" / "poison"
                if target_id and (player_id or snapshot.player_id):
                    try:
                        actor_id = player_id or snapshot.player_id
                        # 女巫解药需要传入刀口信息用于校验
                        game = get_game_state(game_id)
                        actor = next((p for p in game.players if p.id == actor_id), None)
                        witch_wolf_target_id = None
                        if actor and actor.role == RoleType.witch and action_type == "save":
                            # 从已提交的狼人行动中计算刀口
                            wolf_targets = []
                            for action in game.night_actions:
                                if str(action.get("role", "")) == RoleType.wolf.value:
                                    wolf_targets.append(str(action.get("targetId", "")))
                            if wolf_targets:
                                tally = {}
                                for tid in wolf_targets:
                                    tally[tid] = tally.get(tid, 0) + 1
                                witch_wolf_target_id = max(tally, key=tally.get)
                        record_night_action(game_id, actor_id, target_id, action_type, witch_wolf_target_id)
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
            elif message_type == "sheriff_campaign":
                # 警长竞选：上警或退选
                action = str(payload.get("action", "")).strip()  # "run" 或 "withdraw"
                if player_id:
                    try:
                        if action == "run":
                            register_sheriff_campaign(game_id, player_id)
                            game = get_game_state(game_id)
                            player = next((p for p in game.players if p.id == player_id), None)
                            display_name = f"{player.seat_number}号({player.name})" if player else "玩家"
                            await manager.broadcast(
                                game_id,
                                SocketMessage(
                                    type=MessageType.sheriff_campaign,
                                    timestamp=utc_now_iso(),
                                    payload={
                                        "action": "run",
                                        "playerId": player_id,
                                        "playerName": display_name,
                                        "candidateIds": game.sheriff_candidate_ids,
                                    },
                                ).model_dump_json(),
                            )
                        elif action == "withdraw":
                            withdraw_sheriff_campaign(game_id, player_id)
                            game = get_game_state(game_id)
                            player = next((p for p in game.players if p.id == player_id), None)
                            display_name = f"{player.seat_number}号({player.name})" if player else "玩家"
                            await manager.broadcast(
                                game_id,
                                SocketMessage(
                                    type=MessageType.sheriff_campaign,
                                    timestamp=utc_now_iso(),
                                    payload={
                                        "action": "withdraw",
                                        "playerId": player_id,
                                        "playerName": display_name,
                                        "candidateIds": game.sheriff_candidate_ids,
                                    },
                                ).model_dump_json(),
                            )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "sheriff_vote":
                # 警长竞选投票
                target_id = str(payload.get("targetId", "")).strip()
                effective_target = target_id if target_id and target_id != "abstain" else "abstain"
                if player_id:
                    try:
                        record_sheriff_vote(game_id, player_id, effective_target)
                        await manager.send_to(
                            websocket,
                            SocketMessage(
                                type=MessageType.announce,
                                timestamp=utc_now_iso(),
                                payload={"content": "警长竞选投票已提交"},
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "wolf_self_destruct":
                # 狼人自爆
                if player_id:
                    try:
                        result = wolf_self_destruct(game_id, player_id)
                        destruct_name = result.get("player_name", "某玩家")
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.wolf_self_destruct,
                                timestamp=utc_now_iso(),
                                payload={
                                    "playerId": player_id,
                                    "playerName": destruct_name,
                                    "playerRole": "wolf",
                                },
                            ).model_dump_json(),
                        )
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.player_update,
                                timestamp=utc_now_iso(),
                                payload={
                                    "playerId": player_id,
                                    "isAlive": False,
                                    "playerName": destruct_name,
                                },
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "sheriff_transfer":
                # 警长转让徽章
                target_id = str(payload.get("targetId", "")).strip()
                if player_id and target_id:
                    try:
                        transfer_sheriff_badge(game_id, player_id, target_id)
                        game = get_game_state(game_id)
                        target = next((p for p in game.players if p.id == target_id), None)
                        target_name = f"{target.seat_number}号({target.name})" if target else "玩家"
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.sheriff_transfer,
                                timestamp=utc_now_iso(),
                                payload={
                                    "fromPlayerId": player_id,
                                    "toPlayerId": target_id,
                                    "toPlayerName": target_name,
                                },
                            ).model_dump_json(),
                        )
                        await manager.broadcast(
                            game_id,
                            SocketMessage(
                                type=MessageType.player_update,
                                timestamp=utc_now_iso(),
                                payload={
                                    "playerId": target_id,
                                    "isAlive": True,
                                    "playerName": target_name,
                                    "isSheriff": True,
                                },
                            ).model_dump_json(),
                        )
                    except AppError as exc:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": exc.message}).model_dump_json(),
                        )
            elif message_type == "speak_direction":
                # 警长选择发言方向
                direction = str(payload.get("direction", "")).strip()
                if player_id and direction in ("left", "right"):
                    game = get_game_state(game_id)
                    # 校验：只有当前警长可以发送此消息
                    if game.sheriff_id == player_id:
                        game.speak_direction = direction
                        await manager.send_to(
                            websocket,
                            SocketMessage(
                                type=MessageType.speak_direction,
                                timestamp=utc_now_iso(),
                                payload={"direction": direction},
                            ).model_dump_json(),
                        )
                    else:
                        await manager.send_to(
                            websocket,
                            SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": "只有警长可以选择发言方向"}).model_dump_json(),
                        )
                else:
                    await manager.send_to(
                        websocket,
                        SocketMessage(type=MessageType.error, timestamp=utc_now_iso(), payload={"content": "发言方向只能是 left 或 right"}).model_dump_json(),
                    )
            elif message_type == "hunter_shoot":
                # 猎人开枪
                target_id = str(payload.get("targetId", "")).strip()
                if target_id and player_id:
                    game = get_game_state(game_id)
                    if game.pending_hunter_shoot == player_id:
                        target = next((p for p in game.players if p.id == target_id), None)
                        if target and target.is_alive and target.id != player_id:
                            target.is_alive = False
                            game.pending_hunter_shoot = None
                            hunter = next((p for p in game.players if p.id == player_id), None)
                            hunter_name = f"{hunter.seat_number}号({hunter.name})" if hunter else "猎人"
                            target_name = f"{target.seat_number}号({target.name})"
                            await manager.broadcast(
                                game_id,
                                SocketMessage(
                                    type=MessageType.announce,
                                    timestamp=utc_now_iso(),
                                    payload={"content": f"🔫 {hunter_name} 开枪带走了 {target_name}！"},
                                ).model_dump_json(),
                            )
                            await manager.broadcast(
                                game_id,
                                SocketMessage(
                                    type=MessageType.player_update,
                                    timestamp=utc_now_iso(),
                                    payload={
                                        "playerId": target_id,
                                        "isAlive": False,
                                        "playerName": target_name,
                                    },
                                ).model_dump_json(),
                            )

                            # 检查被枪杀玩家是否是警长
                            if game.sheriff_id == target_id:
                                from app.services.game_service import transfer_sheriff_badge as _transfer_sheriff
                                # 警长被枪杀，需要转让徽章（由 Judge 处理，这里仅标记）
                                pass

                            # 检查胜负
                            from app.domain.roles import get_preset_rule
                            win_condition = get_preset_rule(game.room_settings.scene.preset, "win_condition")
                            winner = _check_win_condition(game, win_condition)
                            if winner:
                                game.winner_faction = winner
                                game.game_status = GameStatus.end
                                await manager.broadcast(
                                    game_id,
                                    SocketMessage(
                                        type=MessageType.game_over,
                                        timestamp=utc_now_iso(),
                                        payload={
                                            "gameId": game_id,
                                            "winnerFaction": winner,
                                            "currentRound": game.current_round,
                                        },
                                    ).model_dump_json(),
                                )
            elif message_type == "role_select_choice":
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
