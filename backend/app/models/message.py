from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Index
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
    __table_args__ = (
        Index("ix_message_session_id_sequence", "session_id", "sequence"),
    )

    session_id: UUID = Field(foreign_key="session.id")
    sequence: int
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    session: Optional["Session"] = Relationship(back_populates="messages")
