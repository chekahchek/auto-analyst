from typing import TYPE_CHECKING, List

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import CreatedAtBase, UUIDBase

if TYPE_CHECKING:
    from app.models.dataset import Dataset


class User(UUIDBase, CreatedAtBase, SQLModel, table=True):
    __tablename__ = "user"

    email: str = Field(index=True, unique=True)

    datasets: List["Dataset"] = Relationship(back_populates="user")
