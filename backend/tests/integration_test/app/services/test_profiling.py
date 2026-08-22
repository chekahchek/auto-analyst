import pytest

from app.database import AsyncSessionLocal
from app.models.dataset import Dataset
from app.services.profiling import update_dataset_profile


pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("apply_migrations")]


async def test_update_dataset_profile_updates_db(monkeypatch):
    profile = {"data_type": ["numeric", "categorical"]}

    async def fake_run_profiler_graph(_storage_path, _graph, _max_llm_calls):
        return profile

    monkeypatch.setattr(
        "app.services.profiling.run_profiler_graph", fake_run_profiler_graph
    )

    dataset = Dataset(
        original_filename="test.csv",
        storage_path="/tmp/test.csv",
    )

    try:
        async with AsyncSessionLocal() as session:
            session.add(dataset)
            await session.commit()
            await session.refresh(dataset)

        await update_dataset_profile(dataset.id, "/tmp/test.csv", None, 5)

        async with AsyncSessionLocal() as session:
            updated = await session.get(Dataset, dataset.id)
            assert updated.data_type == '["numeric", "categorical"]'
    finally:
        async with AsyncSessionLocal() as session:
            row = await session.get(Dataset, dataset.id)
            if row:
                await session.delete(row)
                await session.commit()
