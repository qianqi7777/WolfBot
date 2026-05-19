from fastapi import APIRouter, Query

from app.domain.enums import MessageType
from app.schemas.game import AiConnectionTestResult, CreateGameRequest, GameSnapshot, JoinGameRequest, RoomSettingsUpdate
from app.schemas.socket import SocketMessage
from app.services.ai_service import test_ai_connection
from app.services.game_service import update_room_settings
from app.services.room_service import create_room, get_room, join_room, start_room
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=GameSnapshot)
async def create_room_route(payload: CreateGameRequest) -> GameSnapshot:
    return create_room(payload.player_name)


@router.post("/{game_id}/join", response_model=GameSnapshot)
async def join_room_route(game_id: str, payload: JoinGameRequest) -> GameSnapshot:
    snapshot = join_room(game_id, payload.player_name)
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
async def test_ai_connection_route(game_id: str) -> AiConnectionTestResult:
    return await test_ai_connection(game_id)


@router.post("/{game_id}/start", response_model=GameSnapshot)
async def start_room_route(game_id: str) -> GameSnapshot:
    return start_room(game_id)
