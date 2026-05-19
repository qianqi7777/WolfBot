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


class VoteRequest(BaseSchema):
    target_id: str = Field(alias="targetId", min_length=1)


class GameSnapshot(BaseSchema):
    game_id: str
    player_id: str
    game_status: GameStatus
    players: list[Player]
    my_role: RoleType = RoleType.unknown


class GameResult(BaseSchema):
    winner_faction: str = "pending"
    players: list[Player]
