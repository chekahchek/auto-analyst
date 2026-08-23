from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END

from app.agents.analyst.nodes import (
    analyst_node,
    parse_analyst_output_node,
    should_continue,
    storyteller_node,
)
from app.agents.analyst.states import AnalystState
from app.agents.analyst.tools import SUBMIT_TOOL_NAME
from app.agents.analyst.prompts import ANALYST_SYSTEM_PROMPT_TEMPLATE
from app.agents.analyst.nodes import form_analyst_system_prompt


def make_state(**overrides) -> AnalystState:
    defaults = {
        "dataset_path": "/tmp/test.csv",
        "profile": {"data_type": ["panel"]},
        "messages": [HumanMessage(content="Generate insights")],
        "hypotheses_evidence": None,
        "narrative": None,
        "dashboard_path": None,
        "dashboard_html": None,
        "critic_score": None,
        "critic_feedback": None,
        "iteration_count": 0,
        "llm_calls": 1,
        "max_llm_calls": 3,
    }
    defaults.update(overrides)
    return AnalystState(**defaults)


def test_form_analyst_system_prompt():
    _evidence_chart = {
        "title": "title",
        "insight_index": 0,
        "description": "description",
        "figure": {"data": [], "layout": {}},
    }
    _hypotheses_evidence = {"insights": [""], "charts": [_evidence_chart]}
    state_with_artifacts = make_state()
    state_with_artifacts["hypotheses_evidence"] = _hypotheses_evidence
    state_with_dashboard = make_state(dashboard_path="/dashboards/1.html")
    state = make_state()
    expected_prompt_without_artifacts = ANALYST_SYSTEM_PROMPT_TEMPLATE.format(
        dataset_path=state["dataset_path"],
        data_type=state["profile"]["data_type"][0],
    )
    assert form_analyst_system_prompt(state) == expected_prompt_without_artifacts
    assert "Hypotheses and evidence" in form_analyst_system_prompt(state_with_artifacts)
    dashboard_prompt = form_analyst_system_prompt(state_with_dashboard)
    assert "dashboard HTML" in dashboard_prompt
    assert "read_dashboard_html" in dashboard_prompt
    assert "/dashboards/1.html" in dashboard_prompt


def test_analyst_node():
    model_response = AIMessage(content="")
    model = MagicMock()
    model.invoke.return_value = model_response

    state = make_state()
    result = analyst_node(state, model)

    model.invoke.assert_called_once()
    call_args = model.invoke.call_args[0][0]
    assert isinstance(call_args[0], SystemMessage)
    assert call_args[1] == HumanMessage(content="Generate insights")
    assert result == {"messages": [model_response], "llm_calls": 2}


def test_parse_analyst_output_node():
    args = {"insights": ["a"], "charts": []}
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "some_tool", "args": {}},
                    {"id": "call_2", "name": SUBMIT_TOOL_NAME, "args": args},
                ],
            )
        ]
    )
    assert parse_analyst_output_node(state) == {"hypotheses_evidence": args}


def test_should_continue_parse():
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": SUBMIT_TOOL_NAME,
                        "args": {"insights": ["x"]},
                    }
                ],
            )
        ]
    )
    assert should_continue(state) == "parse"


def test_should_continue_tools():
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "execute_python_script",
                        "args": {"code": "print(1)"},
                    }
                ],
            )
        ]
    )
    assert should_continue(state) == "analyst_tools"


def test_should_continue_conversational():
    state = make_state(
        messages=[AIMessage(content="Sure, what would you like to know?")]
    )
    assert should_continue(state) == END


def test_should_continue_over_budget():
    state = make_state(
        llm_calls=3,
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "execute_python_script",
                        "args": {"code": "x"},
                    }
                ],
            )
        ],
    )
    assert should_continue(state) == END


def test_storyteller_node(tmp_path, monkeypatch):
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = "storytelling instructions"
    monkeypatch.setattr(
        "app.agents.analyst.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    narrative = {"central_question": "Why?", "slides": [], "charts": []}
    model = MagicMock()
    model.invoke.return_value = narrative

    state = make_state(hypotheses_evidence={"insights": ["a"], "charts": []})
    result = storyteller_node(state, model, tmp_path)

    read_skill_instructions.invoke.assert_called_once_with(
        {"skill_name": "core/storytelling"}
    )
    assert result == {"narrative": narrative}
