from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampBase, UUIDBase

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.dataset import Dataset
    from app.models.message import Message


class Session(UUIDBase, TimestampBase, SQLModel, table=True):
    __tablename__ = "session"

    dataset_id: UUID = Field(foreign_key="dataset.id", index=True)

    dataset: Optional["Dataset"] = Relationship(back_populates="sessions")
    messages: List["Message"] = Relationship(back_populates="session")
    artifacts: List["Artifact"] = Relationship(back_populates="session")
