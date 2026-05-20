from fastapi import APIRouter, Query

from app.domain.enums import MessageType
from app.schemas.game import CreateGameRequest, GameResult, GameSnapshot, JoinGameRequest, NightActionRequest, SpeakRequest, VoteRequest
from app.schemas.socket import SocketMessage
from app.services.game_service import (
    create_game,
    get_game,
    get_game_state,
    get_result,
    join_game,
    record_night_action,
    record_speak,
    record_vote,
    start_game,
)
from app.utils.time import utc_now_iso
from app.services.ai_service import launch_ai_cycle
from app.websocket.broadcaster import manager

router = APIRouter(prefix="/games", tags=["games"])


@router.post("", response_model=GameSnapshot)
async def create_game_route(payload: CreateGameRequest) -> GameSnapshot:
    return create_game(payload.player_name)


@router.post("/{game_id}/join", response_model=GameSnapshot)
async def join_game_route(game_id: str, payload: JoinGameRequest) -> GameSnapshot:
    snapshot = join_game(game_id, payload.player_name)
    await manager.broadcast(
        game_id,
        SocketMessage(
            type=MessageType.room_update,
            timestamp=utc_now_iso(),
            payload={
                "gameId": snapshot.game_id,
                "players": [player.model_dump(by_alias=True) for player in snapshot.players],
                "currentSpeakerId": snapshot.current_speaker_id,
                "roomSettings": snapshot.room_settings.model_dump(by_alias=True),
            },
        ).model_dump_json(),
    )
    return snapshot


@router.get("/{game_id}", response_model=GameSnapshot)
async def get_game_route(game_id: str, playerId: str | None = Query(None, alias="playerId")) -> GameSnapshot:
    return get_game(game_id, requester_id=playerId)


@router.post("/{game_id}/start", response_model=GameSnapshot)
async def start_game_route(game_id: str) -> GameSnapshot:
    snapshot = start_game(game_id)
    launch_ai_cycle(game_id)
    await manager.broadcast(
        game_id,
        SocketMessage(
            type=MessageType.game_status,
            timestamp=utc_now_iso(),
            payload={
                "status": snapshot.game_status.value,
                "currentRound": snapshot.current_round,
                "currentSpeakerId": snapshot.current_speaker_id,
                "gameMode": snapshot.game_mode,
            },
        ).model_dump_json(),
    )
    # 抢身份模式下不立即推送角色信息，等抢身份阶段结束后由 Judge 发送
    if snapshot.game_status.value != "role_select":
        from app.services.game_service import get_game_state
        game = get_game_state(game_id)
        for player in game.players:
            if not player.is_ai:
                role_msg = SocketMessage(
                    type=MessageType.role_info,
                    timestamp=utc_now_iso(),
                    payload={"role": player.role.value},
                ).model_dump_json()
                await manager.send_to_player(game_id, player.id, role_msg)
    return snapshot


@router.post("/{game_id}/action/speak")
async def speak_route(game_id: str, payload: SpeakRequest) -> dict[str, str]:
    record_speak(game_id, payload.player_id, payload.content)
    # 广播发言消息，确保所有玩家（包括发言者自己）能看到
    game = get_game_state(game_id)
    speaker = next((p for p in game.players if p.id == payload.player_id), None)
    display_name = f"{speaker.seat_number}号({speaker.name})" if speaker else "玩家"
    await manager.broadcast(
        game_id,
        SocketMessage(
            type=MessageType.player_speak,
            timestamp=utc_now_iso(),
            payload={
                "content": payload.content,
                "playerId": payload.player_id,
                "playerName": display_name,
                "isAI": speaker.is_ai if speaker else False,
            },
        ).model_dump_json(),
    )
    return {"status": "accepted"}


@router.post("/{game_id}/action/vote")
async def vote_route(game_id: str, payload: VoteRequest) -> dict[str, str]:
    record_vote(game_id, payload.player_id, payload.target_id)
    await manager.broadcast(
        game_id,
        SocketMessage(
            type=MessageType.vote_result,
            timestamp=utc_now_iso(),
            payload={"targetId": payload.target_id, "voterId": payload.player_id},
        ).model_dump_json(),
    )
    return {"status": "accepted"}


@router.post("/{game_id}/action/night")
async def night_action_route(game_id: str, payload: NightActionRequest) -> dict[str, str]:
    record_night_action(game_id, payload.player_id, payload.target_id, payload.action_type)
    return {"status": "accepted"}


@router.get("/{game_id}/result", response_model=GameResult)
async def result_route(game_id: str) -> GameResult:
    return get_result(game_id)
