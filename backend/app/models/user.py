from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampBase, UUIDBase

if TYPE_CHECKING:
    from app.models.dataset import Dataset


class User(UUIDBase, TimestampBase, SQLModel, table=True):
    __tablename__ = "user"

    email: str = Field(index=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    datasets: List["Dataset"] = Relationship(back_populates="user")
