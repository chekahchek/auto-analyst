from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks
from starlette.datastructures import UploadFile

from app.models import User
from app.routers.datasets import create_dataset


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
