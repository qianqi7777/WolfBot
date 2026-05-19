from fastapi import APIRouter

from app.schemas.game import CreateGameRequest, GameResult, GameSnapshot, JoinGameRequest, SpeakRequest, VoteRequest
from app.services.game_service import create_game, get_game, get_result, join_game, record_speak, record_vote

router = APIRouter(prefix="/games", tags=["games"])


@router.post("", response_model=GameSnapshot)
async def create_game_route(payload: CreateGameRequest) -> GameSnapshot:
    return create_game(payload.player_name)


@router.post("/{game_id}/join", response_model=GameSnapshot)
async def join_game_route(game_id: str, payload: JoinGameRequest) -> GameSnapshot:
    return join_game(game_id, payload.player_name)


@router.get("/{game_id}", response_model=GameSnapshot)
async def get_game_route(game_id: str) -> GameSnapshot:
    return get_game(game_id)


@router.post("/{game_id}/action/speak")
async def speak_route(game_id: str, payload: SpeakRequest) -> dict[str, str]:
    record_speak(game_id, payload.content)
    return {"status": "accepted"}


@router.post("/{game_id}/action/vote")
async def vote_route(game_id: str, payload: VoteRequest) -> dict[str, str]:
    record_vote(game_id, payload.target_id)
    return {"status": "accepted"}


@router.get("/{game_id}/result", response_model=GameResult)
async def result_route(game_id: str) -> GameResult:
    return get_result(game_id)
