from pydantic import Field

from app.domain.enums import MessageType
from app.schemas.base import BaseSchema


class SocketMessage(BaseSchema):
    type: MessageType
    timestamp: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
