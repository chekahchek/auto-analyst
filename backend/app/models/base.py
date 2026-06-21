from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class UUIDBase(SQLModel):
    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": func.gen_random_uuid()},
    )


def _utc_now() -> datetime:
    """Return a naive UTC datetime matching the DB's TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampBase(SQLModel):
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )
