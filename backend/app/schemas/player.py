from pydantic import Field

from app.domain.enums import RoleType
from app.schemas.base import BaseSchema


class Player(BaseSchema):
    id: str
    name: str
    seat_number: int = Field(default=0, alias="seatNumber", ge=0)
    role: RoleType = RoleType.unknown
    is_ai: bool = Field(default=False, alias="isAI")
    is_alive: bool = True
    night_action_done: bool = False
    last_guard_target_id: str | None = Field(default=None, alias="lastGuardTargetId")
    vote_immunity_used: bool = False  # 白痴翻牌免疫已使用
    is_sheriff: bool = False  # 是否是警长
    antidote_used: bool = False  # 女巫解药已使用
    poison_used: bool = False  # 女巫毒药已使用
    is_spectator: bool = False  # 是否是观战者
