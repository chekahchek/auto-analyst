import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Artifact, Dataset, Message, MessageRole, Session


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations")]


async def _create_session(db: AsyncSession) -> Session:
    dataset = Dataset(original_filename="data.csv", storage_path="/tmp/data.csv")
    db.add(dataset)
    await db.flush()
    session = Session(dataset_id=dataset.id)
    db.add(session)
    await db.flush()
    return session


def _message(session_id, sequence: int) -> Message:
    return Message(
        session_id=session_id,
        sequence=sequence,
        role=MessageRole.USER,
        content="question",
    )


async def test_message_sequence_is_unique_within_a_session():
    async with AsyncSessionLocal() as db:
        session = await _create_session(db)
        db.add(_message(session.id, 1))
        db.add(_message(session.id, 1))

        with pytest.raises(IntegrityError):
            await db.flush()


async def test_message_sequence_can_repeat_across_sessions():
    async with AsyncSessionLocal() as db:
        first = await _create_session(db)
        second = await _create_session(db)
        db.add(_message(first.id, 1))
        db.add(_message(second.id, 1))

        await db.flush()


async def test_artifact_iteration_is_unique_within_a_session():
    async with AsyncSessionLocal() as db:
        session = await _create_session(db)
        db.add(Artifact(session_id=session.id, iteration=1))
        db.add(Artifact(session_id=session.id, iteration=1))

        with pytest.raises(IntegrityError):
            await db.flush()
