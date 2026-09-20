from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import app.dependencies as dependencies
from app.models import User


@pytest.mark.asyncio
async def test_get_current_user_requires_development_identity_header():
    db = Mock()
    db.exec = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(db=db, x_user_email=None)

    assert exc_info.value.status_code == 401
    db.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_returns_existing_user():
    user = User(email="existing@example.com")
    result = Mock()
    result.one_or_none.return_value = user
    db = Mock()
    db.exec = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    actual = await dependencies.get_current_user(
        db=db,
        x_user_email=" Existing@Example.com ",
    )

    assert actual is user
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_user():
    result = Mock()
    result.one_or_none.return_value = None
    db = Mock()
    db.exec = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await dependencies.get_current_user(
            db=db,
            x_user_email="unknown@example.com",
        )

    assert exc_info.value.status_code == 401
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()
