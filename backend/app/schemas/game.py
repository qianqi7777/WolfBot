from typing import Any

from pydantic import Field, model_validator

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


class SceneConfig(BaseSchema):
    preset: str = Field(default="six-player-dark", alias="preset")
    name: str = Field(default="6人暗牌场", alias="name")
    description: str = Field(
        default="2狼4好人，神职为预言家和守卫，暗牌局，无警长，节奏快。",
        alias="description",
    )
    player_count: int = Field(default=6, alias="playerCount", ge=2, le=18)

    @model_validator(mode="before")
    @classmethod
    def enforce_six_player_preset(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("preset") == "six-player-dark":
            if "playerCount" in data:
                data["playerCount"] = 6
            elif "player_count" in data:
                data["player_count"] = 6
            else:
                data["playerCount"] = 6
        return data


class AiConfigInput(BaseSchema):
    base_url: str = Field(default="", alias="baseUrl")
    api_key: str = Field(default="", alias="apiKey")
    model: str = Field(default="gpt-4o-mini", alias="model")
    timeout_seconds: float = Field(default=20.0, alias="timeoutSeconds", gt=0)
    temperature: float = Field(default=0.7, alias="temperature", ge=0, le=2)
    enable_mock: bool = Field(default=True, alias="enableMock")


class AiConfigView(BaseSchema):
    base_url: str = Field(default="", alias="baseUrl")
    model: str = Field(default="gpt-4o-mini", alias="model")
    timeout_seconds: float = Field(default=20.0, alias="timeoutSeconds")
    temperature: float = Field(default=0.7, alias="temperature")
    enable_mock: bool = Field(default=True, alias="enableMock")
    has_api_key: bool = Field(default=False, alias="hasApiKey")


class RoomSettingsUpdate(BaseSchema):
    scene: SceneConfig
    ai: AiConfigInput


class RoomSettings(BaseSchema):
    scene: SceneConfig
    ai: AiConfigView


class GameSnapshot(BaseSchema):
    game_id: str
    player_id: str
    game_status: GameStatus
    current_round: int = 1
    started: bool = False
    winner_faction: str | None = None
    players: list[Player]
    my_role: RoleType = RoleType.unknown
    night_action_required: bool = False
    room_settings: RoomSettings


class NightActionRequest(BaseSchema):
    player_id: str = Field(alias="playerId", min_length=1)
    target_id: str = Field(alias="targetId", min_length=1)


class GameResult(BaseSchema):
    game_id: str
    winner_faction: str = "pending"
    current_round: int = 1
    players: list[Player]
    chats: list[dict[str, object]] = Field(default_factory=list)
    announcements: list[str] = Field(default_factory=list)
