from fastapi import APIRouter, Query

from app.domain.enums import MessageType
from app.schemas.game import AiConfigInput, AiConnectionTestResult, ChangeSeatRequest, CreateGameRequest, GameSnapshot, JoinGameRequest, RoomSettingsUpdate
from app.schemas.socket import SocketMessage
from app.services.ai_service import test_ai_connection
from app.services.game_service import update_room_settings
from app.services.room_service import change_room_seat, create_room, get_room, join_room, start_room
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=GameSnapshot)
async def create_room_route(payload: CreateGameRequest) -> GameSnapshot:
    return create_room(payload.player_name)


@router.post("/{game_id}/join", response_model=GameSnapshot)
async def join_room_route(game_id: str, payload: JoinGameRequest) -> GameSnapshot:
    snapshot = join_room(game_id, payload.player_name, payload.preferred_seat)
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
async def get_room_route(game_id: str, playerId: str | None = Query(None, alias="playerId")) -> GameSnapshot:
    return get_room(game_id, requester_id=playerId)


@router.put("/{game_id}/seat", response_model=GameSnapshot)
async def change_seat_route(game_id: str, payload: ChangeSeatRequest) -> GameSnapshot:
    snapshot = change_room_seat(game_id, payload.player_id, payload.seat_number)
    await manager.broadcast(
        game_id,
        SocketMessage(
            type=MessageType.room_update,
            timestamp=utc_now_iso(),
            payload={
                "gameId": snapshot.game_id,
                "players": [player.model_dump(by_alias=True) for player in snapshot.players],
                "roomSettings": snapshot.room_settings.model_dump(by_alias=True),
            },
        ).model_dump_json(),
    )
    return snapshot


@router.patch("/{game_id}/settings", response_model=GameSnapshot)
async def update_room_settings_route(game_id: str, payload: RoomSettingsUpdate) -> GameSnapshot:
    snapshot = update_room_settings(game_id, payload)
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


@router.post("/{game_id}/ai/test", response_model=AiConnectionTestResult)
async def test_ai_connection_route(game_id: str, payload: AiConfigInput | None = None) -> AiConnectionTestResult:
    from app.services.game_service import AiRuntimeConfig

    runtime_override = None
    if payload and (payload.base_url.strip() or payload.api_key.strip()):
        runtime_override = AiRuntimeConfig(
            base_url=payload.base_url.strip(),
            api_key=payload.api_key.strip(),
            model=payload.model.strip(),
            timeout_seconds=payload.timeout_seconds,
            temperature=payload.temperature,
            enable_mock=False,
        )
    return await test_ai_connection(game_id, runtime_override)


@router.post("/{game_id}/start", response_model=GameSnapshot)
async def start_room_route(game_id: str, playerId: str | None = Query(None, alias="playerId")) -> GameSnapshot:
    snapshot = start_room(game_id, requester_id=playerId)
    # 向真人玩家推送角色信息
    from app.services.game_service import get_game_state
    from app.domain.enums import MessageType
    from app.schemas.socket import SocketMessage
    from app.utils.time import utc_now_iso
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
