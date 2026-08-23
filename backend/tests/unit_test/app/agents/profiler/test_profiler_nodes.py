from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END

from app.agents.profiler.nodes import (
    profiler_node,
    should_continue,
    retry_node,
    build_profiler_graph,
)
from app.agents.profiler.states import ProfilerState
from app.agents.profiler.prompts import RETRY_PROMPT


def test_profiler_node(tmp_path, monkeypatch):
    skill_instructions = "name: profile-data"
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = skill_instructions
    monkeypatch.setattr(
        "app.agents.profiler.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    model_response = AIMessage(content='{"name": "test"}')
    model = MagicMock()
    model.invoke.return_value = model_response

    state: ProfilerState = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=1,
        max_llm_calls=3,
        messages=[HumanMessage(content="Hello")],
    )

    result = profiler_node(state, model, tmp_path)

    read_skill_instructions.invoke.assert_called_once_with(
        {"skill_name": "core/profile-data"}
    )

    model.invoke.assert_called_once()
    call_args = model.invoke.call_args[0][0]
    assert isinstance(call_args[0], SystemMessage)
    assert skill_instructions in call_args[0].content
    assert call_args[1] == HumanMessage(content="Hello")

    assert result == {"messages": [model_response], "llm_calls": 2}


def test_should_continue():
    state_valid_json = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=1,
        max_llm_calls=3,
        messages=[AIMessage(content='{"valid": "json"}')],
    )

    state_invalid_json = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=1,
        max_llm_calls=3,
        messages=[AIMessage(content="not json")],
    )

    state_route_to_tools = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=1,
        max_llm_calls=3,
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "some_tool",
                        "args": {"arg1": "value1"},
                    }
                ],
            )
        ],
    )

    state_over_limit = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=3,
        max_llm_calls=3,
        messages=[AIMessage(content="not json")],
    )

    assert should_continue(state_valid_json) == END
    assert should_continue(state_invalid_json) == "retry"
    assert should_continue(state_route_to_tools) == "tools"
    assert should_continue(state_over_limit) == END


def test_retry_node():
    state: ProfilerState = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=1,
        max_llm_calls=3,
        messages=[AIMessage(content="message")],
    )
    new_state = retry_node(state)
    assert new_state["messages"][0].content == RETRY_PROMPT


async def test_build_profiler_graph(tmp_path, monkeypatch):
    skill_instructions = "name: profile-data"
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = skill_instructions
    monkeypatch.setattr(
        "app.agents.profiler.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    bound_model = MagicMock()
    bound_model.invoke.side_effect = [
        AIMessage(content="not valid json"),
        AIMessage(content='{"data_type": ["numeric"]}'),
    ]
    model = MagicMock()
    model.bind_tools.return_value = bound_model

    graph = build_profiler_graph(tmp_path, model)

    initial_state: ProfilerState = ProfilerState(
        storage_path="/tmp/test.csv",
        llm_calls=0,
        max_llm_calls=2,
        messages=[HumanMessage(content="start")],
    )

    final_state = await graph.ainvoke(initial_state)

    assert len(final_state["messages"]) == 4
    assert final_state["messages"][0].content == "start"
    assert final_state["messages"][1].content == "not valid json"
    assert final_state["messages"][2].content == RETRY_PROMPT
    assert final_state["messages"][3].content == '{"data_type": ["numeric"]}'
    assert final_state["llm_calls"] == 2
