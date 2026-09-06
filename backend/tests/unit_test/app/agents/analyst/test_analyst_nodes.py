from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END

from app.agents.analyst.nodes import (
    analyst_node,
    frontend_designer_node,
    parse_analyst_output_node,
    parse_dashboard_output_node,
    should_continue,
    storyteller_node,
)
from app.agents.analyst.states import AnalystState
from app.agents.analyst.tools import SUBMIT_TOOL_NAME, UPDATE_DASHBOARD_TOOL_NAME
from app.agents.analyst.prompts import (
    ANALYST_SYSTEM_PROMPT_TEMPLATE,
    FRONTEND_DESIGNER_PROMPT_TEMPLATE,
    PLOTLY_FIGURE_TOKEN_TEMPLATE,
)
from app.agents.analyst.nodes import form_analyst_system_prompt


def make_state(**overrides) -> AnalystState:
    defaults = {
        "dataset_path": "/tmp/test.csv",
        "figures_dir": "/tmp/test_run",
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
        "figure": "/tmp/fig_0.json",
    }
    _hypotheses_evidence = {"insights": [""], "charts": [_evidence_chart]}
    state_with_artifacts = make_state()
    state_with_artifacts["hypotheses_evidence"] = _hypotheses_evidence
    state_with_dashboard = make_state(dashboard_path="/dashboards/1.html")
    state = make_state()
    expected_prompt_without_artifacts = ANALYST_SYSTEM_PROMPT_TEMPLATE.format(
        dataset_path=state["dataset_path"],
        data_type=state["profile"]["data_type"][0],
        figures_dir=state["figures_dir"],
    )
    assert form_analyst_system_prompt(state) == expected_prompt_without_artifacts
    assert "Hypotheses and evidence" in form_analyst_system_prompt(state_with_artifacts)
    dashboard_prompt = form_analyst_system_prompt(state_with_dashboard)
    assert "dashboard HTML" in dashboard_prompt
    assert "read_dashboard" in dashboard_prompt
    assert "/dashboards/1.html" in dashboard_prompt


def test_frontend_prompt_uses_plotly_token_template():
    assert (
        PLOTLY_FIGURE_TOKEN_TEMPLATE.format(index="<index>")
        in FRONTEND_DESIGNER_PROMPT_TEMPLATE
    )


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


def test_parse_analyst_output_node_keeps_figure_pointer(tmp_path):
    fig_path = tmp_path / "fig_0.json"
    fig_path.write_text('{"data": [{"type": "scatter"}], "layout": {}}')

    args = {
        "insights": ["a"],
        "charts": [
            {
                "title": "t",
                "insight_index": 0,
                "description": "d",
                "figure": str(fig_path),
            }
        ],
    }
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": SUBMIT_TOOL_NAME, "args": args}],
            )
        ]
    )
    result = parse_analyst_output_node(state)
    # The pointer (path) is kept as-is; the JSON is never loaded into state.
    assert result["hypotheses_evidence"]["charts"][0]["figure"] == str(fig_path)


def test_parse_dashboard_output_node():
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": UPDATE_DASHBOARD_TOOL_NAME,
                        "args": {"dashboard_html": "<html></html>"},
                    },
                ],
            )
        ]
    )
    assert parse_dashboard_output_node(state) == {"dashboard_html": "<html></html>"}


def test_parse_analyst_output_node_missing_raises():
    state = make_state(messages=[AIMessage(content="no insights here")])
    try:
        parse_analyst_output_node(state)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_retry_node():
    from app.agents.analyst.nodes import retry_node

    result = retry_node(make_state())
    assert isinstance(result["messages"][0], SystemMessage)
    assert SUBMIT_TOOL_NAME in result["messages"][0].content


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


def test_should_continue_finalize_dashboard():
    state = make_state(
        messages=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": UPDATE_DASHBOARD_TOOL_NAME,
                        "args": {"dashboard_html": "<html></html>"},
                    }
                ],
            )
        ]
    )
    assert should_continue(state) == "finalize_dashboard"


def test_should_continue_empty_content_routes_to_retry():
    state = make_state(messages=[AIMessage(content="")])
    assert should_continue(state) == "retry"


def test_should_continue_empty_content_over_budget_ends():
    state = make_state(llm_calls=3, messages=[AIMessage(content="")])
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

    model = MagicMock()
    model.invoke.return_value = {"central_question": "Why?", "slides": []}

    state = make_state(hypotheses_evidence={"insights": ["a"], "charts": []})
    result = storyteller_node(state, model, tmp_path)

    read_skill_instructions.invoke.assert_called_once_with(
        {"skill_name": "core/storytelling"}
    )
    assert result == {
        "narrative": {"central_question": "Why?", "slides": [], "charts": []}
    }


def test_storyteller_node_strips_figure_and_keeps_pointer(tmp_path, monkeypatch):
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = "storytelling instructions"
    monkeypatch.setattr(
        "app.agents.analyst.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    model = MagicMock()
    model.invoke.return_value = {"central_question": "Why?", "slides": []}

    figure = "/tmp/fig_0.json"
    charts = [{"title": "t", "insight_index": 0, "description": "d", "figure": figure}]
    state = make_state(hypotheses_evidence={"insights": ["a"], "charts": charts})
    result = storyteller_node(state, model, tmp_path)

    evidence_msg = model.invoke.call_args[0][0][1]
    assert "figure" not in evidence_msg.content
    assert result["narrative"]["charts"][0]["figure"] == figure
    assert "insight_index" not in result["narrative"]["charts"][0]


def test_frontend_designer_node(tmp_path, monkeypatch):
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = "frontend design instructions"
    monkeypatch.setattr(
        "app.agents.analyst.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    html = "<html><body>dashboard</body></html>"
    model = MagicMock()
    model.invoke.return_value = AIMessage(content=html)

    state = make_state(
        narrative={"central_question": "Why?", "slides": [], "charts": []}
    )
    result = frontend_designer_node(state, model, tmp_path)

    read_skill_instructions.invoke.assert_called_once_with(
        {"skill_name": "core/frontend-design"}
    )
    assert result == {"dashboard_html": html}


def test_frontend_designer_node_injects_figure_reference(tmp_path, monkeypatch):
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = "frontend design instructions"
    monkeypatch.setattr(
        "app.agents.analyst.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content=(
            "<html><body>"
            f"{PLOTLY_FIGURE_TOKEN_TEMPLATE.format(index=0)}"
            "</body></html>"
        )
    )

    figure = "/tmp/fig_0.json"
    state = make_state(
        narrative={
            "central_question": "Why?",
            "slides": [],
            "charts": [{"title": "t", "description": "d", "figure": figure}],
        }
    )
    result = frontend_designer_node(state, model, tmp_path)

    html = result["dashboard_html"]
    assert "__PLOTLY_FIGURE_0__" not in html
    assert 'id="plotly-0"' in html
    assert 'data-plotly-figure="fig_0.json"' in html
    assert "/tmp/fig_0.json" not in html
    assert "fetch(" not in html
    assert "Plotly.newPlot" not in html

    narrative_msg = model.invoke.call_args[0][0][1]
    assert "/tmp/fig_0.json" not in narrative_msg.content


def test_frontend_designer_node_strips_markdown_fences(tmp_path, monkeypatch):
    read_skill_instructions = MagicMock()
    read_skill_instructions.invoke.return_value = "frontend design instructions"
    monkeypatch.setattr(
        "app.agents.analyst.nodes.build_read_skill_instructions_tool",
        lambda _skills_dir: read_skill_instructions,
    )

    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content="```html\n<!doctype html><html></html>\n```"
    )

    state = make_state(
        narrative={"central_question": "Why?", "slides": [], "charts": []}
    )
    result = frontend_designer_node(state, model, tmp_path)

    assert result["dashboard_html"] == "<!doctype html><html></html>"
