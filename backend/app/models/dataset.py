from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimestampBase, UUIDBase

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.user import User


class Dataset(UUIDBase, TimestampBase, SQLModel, table=True):
    __tablename__ = "dataset"

    user_id: Optional[UUID] = Field(
        default=None,
        foreign_key="user.id",
        index=True,
    )
    filename: str
    original_filename: str
    storage_path: str
    domain: Optional[str] = None
    data_type: Optional[str] = None

    user: Optional["User"] = Relationship(back_populates="datasets")
    sessions: List["Session"] = Relationship(back_populates="dataset")
