from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import Message, MessageRole, Session, User
from app.routers.sessions import ChatRequest, chat, get_session
from app.services.chat import ChatTurnResult
from app.services.exceptions import AnalysisFailedError, SessionNotFoundError
from app.services.sessions import SessionDetail
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dashboard_html", ["<html><body>dashboard</body></html>", None]
)
async def test_get_session_returns_metadata_messages_and_dashboard(
    tmp_path: Path,
    dashboard_html: str | None,
):
    user = User(email="owner@example.com")
    session = Session(
        dataset_id=uuid4(),
        created_at=datetime(2026, 10, 1, 9, 0),
        updated_at=datetime(2026, 10, 2, 9, 30),
    )
    question = Message(
        session_id=session.id,
        sequence=1,
        role=MessageRole.USER,
        content="Generate insights",
        created_at=datetime(2026, 10, 1, 9, 0),
    )
    answer = Message(
        session_id=session.id,
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Here is what I found.",
        created_at=datetime(2026, 10, 1, 9, 1),
    )
    get_detail = AsyncMock(
        return_value=SessionDetail(
            session=session,
            messages=[question, answer],
            dashboard_html=dashboard_html,
        )
    )
    db = Mock()

    with patch("app.routers.sessions.get_session_detail", get_detail):
        response = await get_session(
            session_id=session.id,
            db=db,
            current_user=user,
            storage_service=DatasetStorageService(tmp_path),
        )

    assert response == {
        "session_id": str(session.id),
        "dataset_id": str(session.dataset_id),
        "created_at": datetime(2026, 10, 1, 9, 0),
        "updated_at": datetime(2026, 10, 2, 9, 30),
        "messages": [
            {
                "id": str(question.id),
                "role": "user",
                "content": "Generate insights",
                "created_at": datetime(2026, 10, 1, 9, 0),
            },
            {
                "id": str(answer.id),
                "role": "assistant",
                "content": "Here is what I found.",
                "created_at": datetime(2026, 10, 1, 9, 1),
            },
        ],
        "dashboard_html": dashboard_html,
    }
    get_detail.assert_awaited_once_with(
        db,
        session_id=session.id,
        user_id=user.id,
        storage_root=tmp_path,
    )


@pytest.mark.asyncio
async def test_get_session_returns_404_when_session_not_found(tmp_path: Path):
    with patch(
        "app.routers.sessions.get_session_detail",
        AsyncMock(side_effect=SessionNotFoundError()),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_session(
                session_id=uuid4(),
                db=Mock(),
                current_user=User(email="owner@example.com"),
                storage_service=DatasetStorageService(tmp_path),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"
