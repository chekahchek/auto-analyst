from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.datastructures import UploadFile

from app.models import Dataset, Session, User
from app.routers.datasets import create_dataset, create_session


@pytest.mark.asyncio
async def test_create_dataset_links_dataset_to_current_user():
    db = Mock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    storage_service = Mock()
    storage_service.save = AsyncMock(
        return_value=Path("data/datasets/dataset/input.csv")
    )
    user = User(email="owner@example.com")
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                profiler_graph=Mock(),
                settings=SimpleNamespace(max_profile_llm_calls=10),
            )
        )
    )

    response = await create_dataset(
        file=UploadFile(file=BytesIO(b"name,value\nexample,1\n"), filename="data.csv"),
        background_tasks=BackgroundTasks(),
        request=request,
        db=db,
        current_user=user,
        storage_service=storage_service,
    )

    dataset = db.add.call_args_list[0].args[0]
    assert dataset.user_id == user.id
    assert response["original_filename"] == "data.csv"


@pytest.mark.asyncio
async def test_create_session_returns_new_session_id_for_owned_dataset():
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path="data/datasets/data/input.csv",
    )
    result = Mock()
    result.one_or_none.return_value = dataset
    db = Mock()
    db.exec = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    response = await create_session(
        dataset_id=dataset.id,
        db=db,
        current_user=user,
    )

    session = db.add.call_args.args[0]
    assert isinstance(session, Session)
    assert session.dataset_id == dataset.id
    assert response == {"session_id": str(session.id)}
    assert UUID(response["session_id"]) == session.id
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_create_session_rejects_dataset_not_owned_by_current_user():
    result = Mock()
    result.one_or_none.return_value = None
    db = Mock()
    db.exec = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await create_session(
            dataset_id=UUID("00000000-0000-0000-0000-000000000001"),
            db=db,
            current_user=User(email="other@example.com"),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Dataset not found"
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
