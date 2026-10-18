from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import User
from app.routers.sessions import ChatRequest, chat
from app.services.chat import ChatTurnResult
from app.services.exceptions import AnalysisFailedError, SessionNotFoundError
from app.services.storage import DatasetStorageService


def _request(graph):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                analyst_graph=graph,
                settings=SimpleNamespace(max_analyst_llm_calls=20),
            )
        )
    )


@pytest.mark.asyncio
async def test_chat_returns_assistant_message_and_dashboard(tmp_path: Path):
    user = User(email="owner@example.com")
    graph = Mock()
    db = Mock()
    session_id = uuid4()
    run_turn = AsyncMock(
        return_value=ChatTurnResult(
            final_message="Current answer",
            dashboard_html="<html><body>dashboard</body></html>",
        )
    )

    with patch("app.routers.sessions.run_chat_turn", run_turn):
        response = await chat(
            session_id=session_id,
            payload=ChatRequest(message="  Current question  "),
            request=_request(graph),
            db=db,
            current_user=user,
            storage_service=DatasetStorageService(tmp_path),
        )

    assert response == {
        "message": {"role": "assistant", "content": "Current answer"},
        "dashboard_html": "<html><body>dashboard</body></html>",
    }
    run_turn.assert_awaited_once_with(
        db,
        session_id=session_id,
        user_id=user.id,
        question="Current question",
        graph=graph,
        max_analyst_llm_calls=20,
        storage_root=tmp_path,
    )


@pytest.mark.asyncio
async def test_chat_returns_404_when_session_not_found(tmp_path: Path):
    with patch(
        "app.routers.sessions.run_chat_turn",
        AsyncMock(side_effect=SessionNotFoundError()),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await chat(
                session_id=uuid4(),
                payload=ChatRequest(message="Hello"),
                request=_request(Mock()),
                db=Mock(),
                current_user=User(email="owner@example.com"),
                storage_service=DatasetStorageService(tmp_path),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"


@pytest.mark.asyncio
async def test_chat_returns_500_with_reference_id_when_analysis_fails(tmp_path: Path):
    reference_id = uuid4()

    with patch(
        "app.routers.sessions.run_chat_turn",
        AsyncMock(side_effect=AnalysisFailedError(reference_id)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await chat(
                session_id=uuid4(),
                payload=ChatRequest(message="Hello"),
                request=_request(Mock()),
                db=Mock(),
                current_user=User(email="owner@example.com"),
                storage_service=DatasetStorageService(tmp_path),
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == f"Analysis failed. Reference ID: {reference_id}"


@pytest.mark.asyncio
async def test_chat_rejects_blank_message(tmp_path: Path):
    run_turn = AsyncMock()

    with patch("app.routers.sessions.run_chat_turn", run_turn):
        with pytest.raises(HTTPException) as exc_info:
            await chat(
                session_id=uuid4(),
                payload=ChatRequest(message="   "),
                request=_request(Mock()),
                db=Mock(),
                current_user=User(email="owner@example.com"),
                storage_service=DatasetStorageService(tmp_path),
            )

    assert exc_info.value.status_code == 422
    run_turn.assert_not_awaited()
