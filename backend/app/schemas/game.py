from typing import Any

from pydantic import Field, model_validator

from app.domain.enums import GameStatus, RoleType
from app.schemas.base import BaseSchema
from app.schemas.player import Player


class CreateGameRequest(BaseSchema):
    player_name: str = Field(alias="playerName", min_length=1, max_length=30)


class JoinGameRequest(BaseSchema):
    player_name: str = Field(alias="playerName", min_length=1, max_length=30)
    preferred_seat: int | None = Field(default=None, alias="preferredSeat", ge=1)


class ChangeSeatRequest(BaseSchema):
    player_id: str = Field(alias="playerId", min_length=1)
    seat_number: int = Field(alias="seatNumber", ge=1)


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
    speak_timeout_seconds: int = Field(default=15, alias="speakTimeoutSeconds", ge=5, le=120,
                                        description="每人发言轮次的超时时间（秒）")
    mode: str = Field(default="classic", alias="mode",
                      description="游戏模式：classic(经典) / role_select(抢身份)")
    rules: dict[str, Any] | None = Field(default=None, alias="rules")

    @model_validator(mode="before")
    @classmethod
    def sync_preset_to_fields(cls, data: Any) -> Any:
        """根据 preset 自动填充 name/description/playerCount/rules"""
        from app.domain.roles import SCENE_PRESETS
        if isinstance(data, dict):
            preset_id = data.get("preset") or data.get("preset_id")
            if preset_id and preset_id in SCENE_PRESETS:
                p = SCENE_PRESETS[preset_id]
                if "name" not in data and "name" not in data:
                    data["name"] = p.name
                if "description" not in data:
                    data["description"] = p.description
                data["playerCount"] = p.player_count
                if "rules" not in data or data.get("rules") is None:
                    data["rules"] = p.rules
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


class AiConnectionTestResult(BaseSchema):
    success: bool
    message: str
    base_url: str = Field(default="", alias="baseUrl")
    model: str = Field(default="gpt-4o-mini", alias="model")
    enable_mock: bool = Field(default=True, alias="enableMock")


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
    current_speaker_id: str | None = Field(default=None, alias="currentSpeakerId")
    started: bool = False
    winner_faction: str | None = None
    players: list[Player]
    my_role: RoleType = RoleType.unknown
    night_action_required: bool = False
    room_settings: RoomSettings
    owner_player_id: str | None = Field(default=None, alias="ownerPlayerId")
    game_mode: str = Field(default="classic", alias="gameMode")


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
    round_events: list[dict[str, object]] = Field(default_factory=list, alias="roundEvents")
    contributions: list[dict[str, object]] = Field(default_factory=list, alias="contributions")
    mvp: dict[str, object] | None = Field(default=None, alias="mvp")
    svp: dict[str, object] | None = Field(default=None, alias="svp")
