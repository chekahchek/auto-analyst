from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.artifact import Artifact
from app.models.dataset import Dataset
from app.models.message import Message
from app.models.session import Session
from app.services.dashboard import load_dashboard_for_delivery
from app.services.exceptions import SessionNotFoundError


@dataclass
class SessionDetail:
    session: Session
    messages: Sequence[Message]
    dashboard_html: str | None


async def load_messages(
    db: AsyncSession,
    session_id: UUID,
) -> Sequence[Message]:
    statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence)
    )
    result = await db.exec(statement)
    return result.all()


async def load_latest_artifact(
    db: AsyncSession,
    session_id: UUID,
) -> Artifact | None:
    statement = (
        select(Artifact)
        .where(Artifact.session_id == session_id)
        .order_by(Artifact.iteration.desc())
        .limit(1)
    )
    result = await db.exec(statement)
    return result.first()


async def get_session_detail(
    db: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
    storage_root: Path,
) -> SessionDetail:
    statement = (
        select(Session)
        .join(Dataset, Dataset.id == Session.dataset_id)
        .where(
            Session.id == session_id,
            Dataset.user_id == user_id,
        )
    )
    result = await db.exec(statement)
    session = result.one_or_none()
    if session is None:
        raise SessionNotFoundError()

    messages = await load_messages(db, session_id)
    artifact = await load_latest_artifact(db, session_id)
    dashboard_html = None
    if artifact is not None and artifact.dashboard_path:
        figures_dir = storage_root / "sessions" / str(session_id) / "figures"
        dashboard_html = await load_dashboard_for_delivery(
            Path(artifact.dashboard_path),
            figures_dir,
        )

    return SessionDetail(
        session=session,
        messages=messages,
        dashboard_html=dashboard_html,
    )
