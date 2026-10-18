from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.models import Artifact, Dataset, Message, MessageRole, Session, User
from app.services.chat import ChatTurnResult, run_chat_turn
from app.services.exceptions import AnalysisFailedError, SessionNotFoundError


def _result(*, one_or_none=None, rows=None, first=None):
    result = Mock()
    result.one_or_none.return_value = one_or_none
    result.all.return_value = rows or []
    result.first.return_value = first
    return result


def _database(*results):
    db = Mock()
    db.exec = AsyncMock(side_effect=list(results))
    db.rollback = AsyncMock()
    db.commit = AsyncMock()
    db.add = Mock()
    return db


@pytest.mark.asyncio
async def test_run_chat_turn_uses_database_history_and_persists_direct_answer(
    tmp_path: Path,
):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
        data_type=["panel"],
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
        _result(first=latest_artifact),
        _result(first=previous_assistant),
    )

    result = await run_chat_turn(
        db,
        session_id=session.id,
        user_id=user.id,
        question="Current question",
        graph=SimpleNamespace(ainvoke=invoke),
        max_analyst_llm_calls=7,
        storage_root=tmp_path,
    )

    assert result == ChatTurnResult(final_message="Current answer", dashboard_html=None)
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
    assert captured_state["max_llm_calls"] == 7

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
    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_chat_turn_defaults_unset_data_type_to_unknown(tmp_path: Path):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
    )
    session = Session(dataset_id=dataset.id)
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
        _result(rows=[]),
        _result(first=None),
        _result(first=None),
    )

    await run_chat_turn(
        db,
        session_id=session.id,
        user_id=user.id,
        question="Generate insights",
        graph=SimpleNamespace(ainvoke=invoke),
        max_analyst_llm_calls=20,
        storage_root=tmp_path,
    )

    assert captured_state["profile"] == {"data_type": "unknown"}


@pytest.mark.asyncio
async def test_run_chat_turn_persists_analysis_artifact_and_materializes_dashboard(
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
    dashboard_html = (
        '<html><body><div id="plotly-0" '
        'data-plotly-figure="fig_0.json"></div></body></html>'
    )

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
            "dashboard_html": dashboard_html,
        }

    db = _database(
        _result(one_or_none=(session, dataset)),
        _result(rows=[]),
        _result(first=None),
        _result(first=None),
    )

    result = await run_chat_turn(
        db,
        session_id=session.id,
        user_id=user.id,
        question="Generate insights",
        graph=SimpleNamespace(ainvoke=invoke),
        max_analyst_llm_calls=20,
        storage_root=tmp_path,
    )

    assert result.final_message == "Generated dashboard"
    assert 'Plotly.newPlot("plotly-0"' in result.dashboard_html
    assert "data-plotly-figure" not in result.dashboard_html
    assert figure["data"][0]["type"] in result.dashboard_html

    dashboard_path = tmp_path / "sessions" / str(session.id) / "dashboard.html"
    assert dashboard_path.read_text(encoding="utf-8") == dashboard_html

    persisted_artifacts = [
        call.args[0]
        for call in db.add.call_args_list
        if isinstance(call.args[0], Artifact)
    ]
    assert len(persisted_artifacts) == 1
    assert persisted_artifacts[0].iteration == 1
    assert persisted_artifacts[0].dashboard_path == str(dashboard_path)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_chat_turn_rejects_session_not_owned_by_user(tmp_path: Path):
    db = _database(_result(one_or_none=None))
    graph = SimpleNamespace(ainvoke=AsyncMock())

    with pytest.raises(SessionNotFoundError):
        await run_chat_turn(
            db,
            session_id=uuid4(),
            user_id=uuid4(),
            question="Hello",
            graph=graph,
            max_analyst_llm_calls=20,
            storage_root=tmp_path,
        )

    graph.ainvoke.assert_not_awaited()
    db.rollback.assert_not_awaited()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_run_chat_turn_updates_existing_dashboard_without_new_artifact(
    tmp_path: Path,
):
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
        _result(first=latest_artifact),
        _result(first=None),
        _result(),
    )

    result = await run_chat_turn(
        db,
        session_id=session.id,
        user_id=user.id,
        question="Update the dashboard",
        graph=SimpleNamespace(ainvoke=invoke),
        max_analyst_llm_calls=20,
        storage_root=tmp_path,
    )

    assert result.dashboard_html == "<html><body>updated</body></html>"
    dashboard_path = tmp_path / "sessions" / str(session.id) / "dashboard.html"
    assert (
        dashboard_path.read_text(encoding="utf-8")
        == "<html><body>updated</body></html>"
    )
    assert not any(isinstance(call.args[0], Artifact) for call in db.add.call_args_list)
    update_params = db.exec.await_args_list[-1].args[0].compile().params
    assert update_params["dashboard_path"] == str(dashboard_path)
    assert latest_artifact.id in update_params.values()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_chat_turn_logs_and_rolls_back_when_graph_fails(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    user = User(email="owner@example.com")
    dataset = Dataset(
        user_id=user.id,
        original_filename="data.csv",
        storage_path=str(tmp_path / "datasets" / "data.csv"),
        data_type="panel",
    )
    session = Session(dataset_id=dataset.id)

    async def invoke(_state):
        raise RuntimeError("LLM unavailable")

    db = _database(
        _result(one_or_none=(session, dataset)),
        _result(rows=[]),
        _result(first=None),
    )

    with pytest.raises(AnalysisFailedError) as exc_info:
        await run_chat_turn(
            db,
            session_id=session.id,
            user_id=user.id,
            question="Generate insights",
            graph=SimpleNamespace(ainvoke=invoke),
            max_analyst_llm_calls=20,
            storage_root=tmp_path,
        )

    assert str(exc_info.value.reference_id) in caplog.text
    assert db.rollback.await_count == 2
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
