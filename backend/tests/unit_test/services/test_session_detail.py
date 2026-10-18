from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models import Artifact, Message, MessageRole, Session
from app.services.exceptions import SessionNotFoundError
from app.services.sessions import get_session_detail


def _result(*, one_or_none=None, rows=None, first=None):
    result = Mock()
    result.one_or_none.return_value = one_or_none
    result.all.return_value = rows or []
    result.first.return_value = first
    return result


def _database(*results):
    db = Mock()
    db.exec = AsyncMock(side_effect=list(results))
    return db


@pytest.mark.asyncio
async def test_get_session_detail_returns_stored_messages(tmp_path: Path):
    session = Session(dataset_id=uuid4())
    messages = [
        Message(
            session_id=session.id,
            sequence=1,
            role=MessageRole.USER,
            content="Generate insights",
        ),
        Message(
            session_id=session.id,
            sequence=2,
            role=MessageRole.ASSISTANT,
            content="Here is what I found.",
        ),
    ]
    db = _database(
        _result(one_or_none=session),
        _result(rows=messages),
        _result(first=None),
    )

    detail = await get_session_detail(
        db,
        session_id=session.id,
        user_id=uuid4(),
        storage_root=tmp_path,
    )

    assert detail.messages == messages


@pytest.mark.asyncio
async def test_get_session_detail_inlines_latest_dashboard_figures(tmp_path: Path):
    session = Session(dataset_id=uuid4())
    session_dir = tmp_path / "sessions" / str(session.id)
    figures_dir = session_dir / "figures"
    figures_dir.mkdir(parents=True)
    (figures_dir / "fig_0.json").write_text(
        '{"data":[{"type":"bar"}],"layout":{}}', encoding="utf-8"
    )
    (session_dir / "dashboard.html").write_text(
        '<html><body><div id="plotly-0" data-plotly-figure="fig_0.json"></div></body></html>',
        encoding="utf-8",
    )
    artifact = Artifact(
        session_id=session.id,
        iteration=1,
        dashboard_path=str(session_dir / "dashboard.html"),
    )
    db = _database(
        _result(one_or_none=session),
        _result(rows=[]),
        _result(first=artifact),
    )

    detail = await get_session_detail(
        db,
        session_id=session.id,
        user_id=uuid4(),
        storage_root=tmp_path,
    )

    assert detail.session is session
    assert 'Plotly.newPlot("plotly-0"' in detail.dashboard_html
    assert "data-plotly-figure" not in detail.dashboard_html


@pytest.mark.asyncio
async def test_get_session_detail_has_no_dashboard_before_first_analysis(
    tmp_path: Path,
):
    session = Session(dataset_id=uuid4())
    db = _database(
        _result(one_or_none=session),
        _result(rows=[]),
        _result(first=None),
    )

    detail = await get_session_detail(
        db,
        session_id=session.id,
        user_id=uuid4(),
        storage_root=tmp_path,
    )

    assert detail.dashboard_html is None


@pytest.mark.asyncio
async def test_get_session_detail_has_no_dashboard_when_artifact_has_no_path(
    tmp_path: Path,
):
    session = Session(dataset_id=uuid4())
    artifact = Artifact(session_id=session.id, iteration=1, dashboard_path=None)
    db = _database(
        _result(one_or_none=session),
        _result(rows=[]),
        _result(first=artifact),
    )

    detail = await get_session_detail(
        db,
        session_id=session.id,
        user_id=uuid4(),
        storage_root=tmp_path,
    )

    assert detail.dashboard_html is None


@pytest.mark.asyncio
async def test_get_session_detail_rejects_session_not_owned_by_user(tmp_path: Path):
    db = _database(_result(one_or_none=None))

    with pytest.raises(SessionNotFoundError):
        await get_session_detail(
            db,
            session_id=uuid4(),
            user_id=uuid4(),
            storage_root=tmp_path,
        )
