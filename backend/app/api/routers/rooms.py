from fastapi import APIRouter

from app.schemas.game import CreateGameRequest, GameSnapshot, JoinGameRequest
from app.services.room_service import create_room, get_room, join_room

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=GameSnapshot)
async def create_room_route(payload: CreateGameRequest) -> GameSnapshot:
    return create_room(payload.player_name)


@router.post("/{game_id}/join", response_model=GameSnapshot)
async def join_room_route(game_id: str, payload: JoinGameRequest) -> GameSnapshot:
    return join_room(game_id, payload.player_name)


@router.get("/{game_id}", response_model=GameSnapshot)
async def get_room_route(game_id: str) -> GameSnapshot:
    return get_room(game_id)
