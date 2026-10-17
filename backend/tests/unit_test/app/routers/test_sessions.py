from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from app.models import Artifact, Dataset, Message, MessageRole, Session, User
from app.routers.sessions import ChatRequest, chat
from app.services.storage import DatasetStorageService


def _result(*, one_or_none=None, rows=None, first=None):
    result = Mock()
    result.one_or_none.return_value = one_or_none
    result.all.return_value = rows or []
    result.first.return_value = first
    return result


def _request(graph, max_analyst_llm_calls=20):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                analyst_graph=graph,
                settings=SimpleNamespace(
                    max_analyst_llm_calls=max_analyst_llm_calls,
                ),
            )
        )
    )


def _database(*results):
    db = Mock()
    db.exec = AsyncMock(side_effect=list(results))
    db.rollback = AsyncMock()
    db.commit = AsyncMock()
    db.add = Mock()
    return db


@pytest.mark.asyncio
async def test_chat_uses_database_history_and_persists_direct_answer(tmp_path: Path):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
        data_type='["panel"]',
    )
    session = Session(dataset_id=dataset.id)
    previous_user = Message(
        session_id=session.id,
        sequence=1,
        role=MessageRole.USER,
        content="Previous question",
    )
    previous_assistant = Message(
        session_id=session.id,
        sequence=2,
        role=MessageRole.ASSISTANT,
        content="Previous answer",
    )
    latest_artifact = Artifact(
        session_id=session.id,
        iteration=1,
        hypotheses_evidence_json={"insights": ["Prior insight"], "charts": []},
        narrative_json={
            "central_question": "Prior question",
            "slides": [],
            "charts": [],
        },
        dashboard_path=str(tmp_path / "sessions" / str(session.id) / "dashboard.html"),
    )

    captured_state = None

    async def invoke(state):
        nonlocal captured_state
        captured_state = state
        return {
            "messages": [AIMessage(content="Current answer")],
            "artifact_action": None,
            "dashboard_html": None,
        }

    db = _database(
        _result(one_or_none=(session, dataset)),
        _result(rows=[previous_user, previous_assistant]),
        _result(rows=[latest_artifact]),
        _result(first=previous_assistant),
    )

    response = await chat(
        session_id=session.id,
        payload=ChatRequest(message="  Current question  "),
        request=_request(SimpleNamespace(ainvoke=invoke)),
        db=db,
        current_user=user,
        storage_service=DatasetStorageService(tmp_path),
    )

    assert response == {
        "message": {"role": "assistant", "content": "Current answer"},
        "dashboard_html": None,
    }
    assert [message.content for message in captured_state["messages"]] == [
        "Previous question",
        "Previous answer",
        "Current question",
    ]
    assert isinstance(captured_state["messages"][0], HumanMessage)
    assert isinstance(captured_state["messages"][1], AIMessage)
    assert (
        captured_state["hypotheses_evidence"]
        == latest_artifact.hypotheses_evidence_json
    )
    assert captured_state["narrative"] == latest_artifact.narrative_json
    assert captured_state["profile"] == {"data_type": ["panel"]}
    assert captured_state["artifact_action"] is None

    persisted_messages = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Message)
    ]
    assert [
        (message.role, message.sequence, message.content)
        for message in persisted_messages
    ] == [
        (MessageRole.USER, 3, "Current question"),
        (MessageRole.ASSISTANT, 4, "Current answer"),
    ]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_persists_analysis_artifact_and_materializes_dashboard(
    tmp_path: Path,
):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
        data_type="time-series",
    )
    session = Session(dataset_id=dataset.id)
    figure = {
        "data": [{"type": "bar", "x": ["Q1"], "y": [1]}],
        "layout": {"title": {"text": "Sales"}},
    }

    async def invoke(state):
        figure_path = Path(state["figures_dir"]) / "fig_0.json"
        figure_path.write_text(
            '{"data":[{"type":"bar","x":["Q1"],"y":[1]}],'
            '"layout":{"title":{"text":"Sales"}}}',
            encoding="utf-8",
        )
        return {
            "messages": [AIMessage(content="Generated dashboard")],
            "artifact_action": "analysis",
            "hypotheses_evidence": {
                "insights": ["Sales increased."],
                "charts": [
                    {
                        "title": "Sales",
                        "insight_index": 0,
                        "description": "Sales by quarter",
                        "figure": str(figure_path),
                    }
                ],
            },
            "narrative": {
                "central_question": "How did sales change?",
                "slides": [],
                "charts": [
                    {
                        "title": "Sales",
                        "description": "Sales by quarter",
                        "figure": str(figure_path),
                    }
                ],
            },
            "dashboard_html": (
                '<html><body><div id="plotly-0" '
                'data-plotly-figure="fig_0.json"></div></body></html>'
            ),
        }

    db = _database(
        _result(one_or_none=(session, dataset)),
        _result(rows=[]),
        _result(rows=[]),
        _result(first=None),
    )

    response = await chat(
        session_id=session.id,
        payload=ChatRequest(message="Generate insights"),
        request=_request(SimpleNamespace(ainvoke=invoke)),
        db=db,
        current_user=user,
        storage_service=DatasetStorageService(tmp_path),
    )

    assert response["message"] == {
        "role": "assistant",
        "content": "Generated dashboard",
    }
    assert 'Plotly.newPlot("plotly-0"' in response["dashboard_html"]
    assert "data-plotly-figure" not in response["dashboard_html"]
    assert figure["data"][0]["type"] in response["dashboard_html"]

    persisted_artifacts = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Artifact)
    ]
    assert len(persisted_artifacts) == 1
    assert persisted_artifacts[0].iteration == 1
    assert persisted_artifacts[0].dashboard_path == str(
        tmp_path / "sessions" / str(session.id) / "dashboard.html"
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_rejects_session_not_owned_by_user(tmp_path: Path):
    user = User(email="owner@example.com")
    db = _database(_result(one_or_none=None))
    graph = SimpleNamespace(ainvoke=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await chat(
            session_id=uuid4(),
            payload=ChatRequest(message="Hello"),
            request=_request(graph),
            db=db,
            current_user=user,
            storage_service=DatasetStorageService(tmp_path),
        )

    assert exc_info.value.status_code == 404
    graph.ainvoke.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_chat_updates_existing_dashboard_without_new_artifact(tmp_path: Path):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
        data_type="panel",
    )
    session = Session(dataset_id=dataset.id)
    latest_artifact = Artifact(
        session_id=session.id,
        iteration=2,
        hypotheses_evidence_json={"insights": ["Prior insight"], "charts": []},
        narrative_json={
            "central_question": "Prior question",
            "slides": [],
            "charts": [],
        },
        dashboard_path=str(tmp_path / "sessions" / str(session.id) / "dashboard.html"),
    )

    async def invoke(_state):
        return {
            "messages": [AIMessage(content="The dashboard has been updated.")],
            "artifact_action": "dashboard_edit",
            "dashboard_html": "<html><body>updated</body></html>",
        }

    db = _database(
        _result(one_or_none=(session, dataset)),
        _result(rows=[]),
        _result(rows=[latest_artifact]),
        _result(first=None),
        _result(),
    )

    response = await chat(
        session_id=session.id,
        payload=ChatRequest(message="Update the dashboard"),
        request=_request(SimpleNamespace(ainvoke=invoke)),
        db=db,
        current_user=user,
        storage_service=DatasetStorageService(tmp_path),
    )

    assert response["dashboard_html"] == "<html><body>updated</body></html>"
    assert not any(isinstance(call.args[0], Artifact) for call in db.add.call_args_list)
    db.commit.assert_awaited_once()
