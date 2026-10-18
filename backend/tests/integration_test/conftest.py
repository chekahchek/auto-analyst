import pytest

from app.database import async_engine


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    # pytest-asyncio runs each test on its own event loop, while pooled asyncpg
    # connections stay bound to the loop that opened them.
    yield
    await async_engine.dispose()
