import pytest
from pathlib import Path
from app.agents.tools import (
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
        "description: Profiles an uploaded dataset to infer type and domain.\n"
        "---\n\n"
        "## Overview\n\n"
        "Analyse the dataset to deduce the type of data and the business domain.\n"
    )
    return skills_dir


def test_build_list_available_skills_tool(skills_dir):
    list_available_skills = build_list_available_skills_tool(skills_dir)
    available_skills = list_available_skills.invoke({})
    assert "core/profile-data" in available_skills


def test_build_read_skill_instructions_tool(skills_dir):
    read_skill_instructions = build_read_skill_instructions_tool(skills_dir)
    profile_data_skill = read_skill_instructions.invoke(
        {"skill_name": "core/profile-data"}
    )
    assert "name: profile-data" in profile_data_skill
