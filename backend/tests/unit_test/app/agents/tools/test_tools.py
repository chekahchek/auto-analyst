import pytest
from pathlib import Path
from app.agents.analyst.tools import build_read_dashboard_html_tool
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


def test_build_read_dashboard_html_tool(tmp_path):
    dashboard = tmp_path / "dashboard.html"
    dashboard.write_text(
        "<html><body>Revenue by decile</body></html>", encoding="utf-8"
    )
    read_dashboard_html = build_read_dashboard_html_tool()
    content = read_dashboard_html.invoke({"file_path": str(dashboard)})
    assert content == "<html><body>Revenue by decile</body></html>"


def test_build_read_dashboard_html_tool_missing_file(tmp_path):
    read_dashboard_html = build_read_dashboard_html_tool()
    result = read_dashboard_html.invoke(
        {"file_path": str(tmp_path / "no_dashboard.html")}
    )
    assert "No dashboard HTML found" in result
