from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Artifact, Dataset, Message, MessageRole, Session, User
from app.services.exceptions import SessionNotFoundError
from app.services.sessions import get_session_detail


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations")]


async def _create_owned_session(db: AsyncSession) -> tuple[User, Session]:
    # Nothing is committed, so closing the session rolls these rows back.
    owner = User(email=f"owner-{uuid4()}@example.com")
    db.add(owner)
    await db.flush()
    dataset = Dataset(
        user_id=owner.id,
        original_filename="data.csv",
        storage_path="/tmp/data.csv",
    )
    db.add(dataset)
    await db.flush()
    session = Session(dataset_id=dataset.id)
    db.add(session)
    await db.flush()
    return owner, session


async def test_get_session_detail_reads_latest_iteration_for_owner_only(
    tmp_path: Path,
):
    async with AsyncSessionLocal() as db:
        owner, session = await _create_owned_session(db)

        session_dir = tmp_path / "sessions" / str(session.id)
        session_dir.mkdir(parents=True)
        (session_dir / "iteration_1.html").write_text(
            "<html>first</html>", encoding="utf-8"
        )
        (session_dir / "dashboard.html").write_text(
            "<html>latest</html>", encoding="utf-8"
        )
        db.add(
            Artifact(
                session_id=session.id,
                iteration=2,
                dashboard_path=str(session_dir / "dashboard.html"),
            )
        )
        db.add(
            Artifact(
                session_id=session.id,
                iteration=1,
                dashboard_path=str(session_dir / "iteration_1.html"),
            )
        )
        await db.flush()

        detail = await get_session_detail(
            db,
            session_id=session.id,
            user_id=owner.id,
            storage_root=tmp_path,
        )

        assert detail.session.id == session.id
        assert detail.dashboard_html == "<html>latest</html>"
        with pytest.raises(SessionNotFoundError):
            await get_session_detail(
                db,
                session_id=session.id,
                user_id=uuid4(),
                storage_root=tmp_path,
            )


async def test_get_session_detail_returns_messages_in_sequence_order(
    tmp_path: Path,
):
    async with AsyncSessionLocal() as db:
        owner, session = await _create_owned_session(db)
        other_session = Session(dataset_id=session.dataset_id)
        db.add(other_session)
        db.add(
            Message(
                session_id=other_session.id,
                sequence=1,
                role=MessageRole.USER,
                content="Other conversation",
            )
        )
        # Inserted out of order so the result depends on the ORDER BY clause.
        db.add(
            Message(
                session_id=session.id,
                sequence=2,
                role=MessageRole.ASSISTANT,
                content="Here is what I found.",
            )
        )
        db.add(
            Message(
                session_id=session.id,
                sequence=1,
                role=MessageRole.USER,
                content="Generate insights",
            )
        )
        await db.flush()

        detail = await get_session_detail(
            db,
            session_id=session.id,
            user_id=owner.id,
            storage_root=tmp_path,
        )

        assert [(message.role, message.content) for message in detail.messages] == [
            (MessageRole.USER, "Generate insights"),
            (MessageRole.ASSISTANT, "Here is what I found."),
        ]
