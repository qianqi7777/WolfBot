from pydantic import Field

from app.domain.enums import GameStatus, RoleType
from app.schemas.base import BaseSchema
from app.schemas.player import Player


class CreateGameRequest(BaseSchema):
    player_name: str = Field(alias="playerName", min_length=1, max_length=30)


class JoinGameRequest(BaseSchema):
    player_name: str = Field(alias="playerName", min_length=1, max_length=30)


class SpeakRequest(BaseSchema):
    content: str = Field(min_length=1, max_length=200)
    player_id: str = Field(alias="playerId", min_length=1)


class VoteRequest(BaseSchema):
    target_id: str = Field(alias="targetId", min_length=1)
    player_id: str = Field(alias="playerId", min_length=1)


class GameSnapshot(BaseSchema):
    game_id: str
    player_id: str
    game_status: GameStatus
    current_round: int = 1
    started: bool = False
    winner_faction: str | None = None
    players: list[Player]
    my_role: RoleType = RoleType.unknown


class GameResult(BaseSchema):
    game_id: str
    winner_faction: str = "pending"
    current_round: int = 1
    players: list[Player]
    chats: list[dict[str, object]] = Field(default_factory=list)
    announcements: list[str] = Field(default_factory=list)
