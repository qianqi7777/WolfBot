from pydantic import Field

from app.domain.enums import RoleType
from app.schemas.base import BaseSchema


class Player(BaseSchema):
    id: str
    name: str
    role: RoleType = RoleType.unknown
    is_ai: bool = Field(default=False, alias="isAI")
    is_alive: bool = True
