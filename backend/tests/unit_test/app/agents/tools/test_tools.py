import pytest
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pathlib import Path
from app.agents.analyst.tools import build_read_dashboard_tool, build_read_figure_tool
from app.agents.common_tools import (
    build_list_available_skills_tool,
    build_read_skill_instructions_tool,
)


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create an isolated skills directory so tests don't depend on git submodules."""
    skills_dir = tmp_path / "skills"
    skill_path = skills_dir / "core" / "profile-data"
    skill_path.mkdir(parents=True)
    skill_path.joinpath("SKILL.md").write_text(
        "---\n"
        "name: profile-data\n"
        "description: Profiles an uploaded dataset to infer data type.\n Used for analysis\n"
        "---\n\n"
        "## Overview\n\n"
        "Analyse the dataset to deduce the type of data.\n"
    )
    return skills_dir


def test_build_list_available_skills_tool(skills_dir):
    list_available_skills = build_list_available_skills_tool(skills_dir)
    available_skills = list_available_skills.invoke({})
    assert "core/profile-data" in available_skills
    assert (
        "Profiles an uploaded dataset to infer data type. Used for analysis"
        in available_skills
    )


def test_build_read_skill_instructions_tool(skills_dir):
    read_skill_instructions = build_read_skill_instructions_tool(skills_dir)
    profile_data_skill = read_skill_instructions.invoke(
        {"skill_name": "core/profile-data"}
    )
    assert "name: profile-data" in profile_data_skill


def test_build_read_dashboard_tool(tmp_path):
    dashboard = tmp_path / "dashboard.html"
    dashboard.write_text(
        "<html><body>Revenue by decile</body></html>", encoding="utf-8"
    )
    read_dashboard = build_read_dashboard_tool()
    content = read_dashboard.invoke({"file_path": str(dashboard)})
    assert content == "<html><body>Revenue by decile</body></html>"


def test_build_read_dashboard_tool_missing_file(tmp_path):
    read_dashboard = build_read_dashboard_tool()
    result = read_dashboard.invoke({"file_path": str(tmp_path / "no_dashboard.html")})
    assert "No dashboard HTML found" in result


def test_build_read_figure_tool(tmp_path):
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    (figures_dir / "fig_0.json").write_text(
        '{"data": [], "layout": {}}', encoding="utf-8"
    )

    read_figure = build_read_figure_tool()
    content = read_figure.invoke(
        {"index": 0, "state": {"figures_dir": str(figures_dir)}}
    )
    assert content == '{"data": [], "layout": {}}'


def test_build_read_figure_tool_missing_file(tmp_path):
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    read_figure = build_read_figure_tool()
    result = read_figure.invoke(
        {"index": 3, "state": {"figures_dir": str(figures_dir)}}
    )
    assert "No figure file found" in result


def test_read_figure_tool_uses_runtime_state(tmp_path):
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    (figures_dir / "fig_0.json").write_text(
        '{"data": [{"type": "bar"}], "layout": {}}', encoding="utf-8"
    )

    class FigureState(TypedDict):
        figures_dir: str
        messages: Annotated[list[BaseMessage], add_messages]

    workflow = StateGraph(FigureState)
    workflow.add_node("tools", ToolNode([build_read_figure_tool()]))
    workflow.add_edge(START, "tools")
    workflow.add_edge("tools", END)
    result = workflow.compile().invoke(
        {
            "figures_dir": str(figures_dir),
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_figure",
                            "args": {"index": 0},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
        }
    )

    assert result["messages"][1].content == (
        '{"data": [{"type": "bar"}], "layout": {}}'
    )
