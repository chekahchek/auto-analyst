from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.session import Session


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(UUIDBase, SQLModel, table=True):
    __tablename__ = "message"

    session_id: UUID = Field(foreign_key="session.id", index=True)
    sequence: int = Field(index=True)
    role: MessageRole
    content: str
    metadata_json: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    session: Optional["Session"] = Relationship(back_populates="messages")
