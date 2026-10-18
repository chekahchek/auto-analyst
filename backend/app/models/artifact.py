from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import CreatedAtBase, UUIDBase

if TYPE_CHECKING:
    from app.models.session import Session


class Artifact(UUIDBase, CreatedAtBase, SQLModel, table=True):
    __tablename__ = "artifact"
    __table_args__ = (
        Index(
            "ix_artifact_session_id_iteration", "session_id", "iteration", unique=True
        ),
    )

    session_id: UUID = Field(foreign_key="session.id")
    iteration: int
    hypotheses_evidence_json: Optional[dict] = Field(
        default=None, sa_column=Column(JSON)
    )
    narrative_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    dashboard_path: Optional[str] = None

    session: Optional["Session"] = Relationship(back_populates="artifacts")
