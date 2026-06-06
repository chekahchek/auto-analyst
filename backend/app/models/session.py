from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampBase, UUIDBase

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.message import Message


class Session(UUIDBase, TimestampBase, SQLModel, table=True):
    __tablename__ = "session"

    dataset_id: UUID = Field(foreign_key="dataset.id", index=True)
    dashboard_path: Optional[str] = None
    cost_spent: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=4)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    dataset: Optional["Dataset"] = Relationship(back_populates="sessions")
    messages: List["Message"] = Relationship(back_populates="session")
