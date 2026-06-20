from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from langgraph.prebuilt import ToolNode
from app.agents.profiler.nodes import (
    call_profiler,
    should_continue,
    retry_node,
    build_profiler_graph,
)
from app.agents.profiler.states import ProfilerState
from app.agents.profiler.prompts import RETRY_PROMPT


def test_call_profiler_invokes_model_with_system_prompt_and_state_messages():
    skill_instructions = "name: profile-data"
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = skill_instructions

    model_response = AIMessage(content='{"name": "test"}')
    model = MagicMock()
    model.invoke.return_value = model_response

    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 1,
        "max_llm_calls": 3,
        "messages": [HumanMessage(content="Hello")],
    }

    result = call_profiler(state, model, read_skill_instructions)

    read_skill_instructions.invoke.assert_called_once_with(
        {"skill_name": "core/profile-data"}
    )

    model.invoke.assert_called_once()
    call_args = model.invoke.call_args[0][0]
    assert isinstance(call_args[0], SystemMessage)
    assert skill_instructions in call_args[0].content
    assert call_args[1] == HumanMessage(content="Hello")

    assert result == {"messages": [model_response], "llm_calls": 2}


@pytest.mark.parametrize(
    "content,expected_key",
    [
        ('{"valid": "json"}', "json_end"),
        ("not json", "retry"),
    ],
)
def test_should_continue_routes_based_on_last_message_content(content, expected_key):
    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 1,
        "max_llm_calls": 3,
        "messages": [AIMessage(content=content)],
    }

    result = should_continue(state)

    if expected_key == "json_end":
        assert result == END
    else:
        assert result == "retry"


def test_should_continue_routes_to_tools_when_tool_calls_present_and_under_limit():
    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 1,
        "max_llm_calls": 3,
        "messages": [
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
    }

    assert should_continue(state) == "tools"


def test_should_continue_ends_when_tool_calls_present_but_over_limit():
    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 3,
        "max_llm_calls": 3,
        "messages": [
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
    }

    assert should_continue(state) == END


def test_should_continue_ends_when_invalid_json_and_over_limit():
    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 3,
        "max_llm_calls": 3,
        "messages": [AIMessage(content="not json")],
    }

    assert should_continue(state) == END


def test_retry_node():
    state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 1,
        "max_llm_calls": 3,
        "messages": [AIMessage(content="message")],
    }
    new_state = retry_node(state)
    assert new_state["messages"][0].content == RETRY_PROMPT


async def test_build_profiler_graph():
    def agent_node_side_effect(state):
        if state["llm_calls"] == 0:
            return {
                "messages": [AIMessage(content="not valid json")],
                "llm_calls": 1,
            }
        return {
            "messages": [
                AIMessage(
                    content='{"data_type": ["numeric"], "business_domain": "finance"}'
                )
            ],
            "llm_calls": 2,
        }

    agent_node = MagicMock(side_effect=agent_node_side_effect)
    graph = build_profiler_graph(agent_node, ToolNode([]), retry_node)

    initial_state: ProfilerState = {
        "storage_path": "/tmp/test.csv",
        "llm_calls": 0,
        "max_llm_calls": 2,
        "messages": [HumanMessage(content="start")],
    }

    final_state = await graph.ainvoke(initial_state)

    assert len(final_state["messages"]) == 4
    assert final_state["messages"][0].content == "start"
    assert final_state["messages"][1].content == "not valid json"
    assert final_state["messages"][2].content == RETRY_PROMPT
    assert final_state["messages"][3].content == (
        '{"data_type": ["numeric"], "business_domain": "finance"}'
    )
    assert final_state["llm_calls"] == 2
