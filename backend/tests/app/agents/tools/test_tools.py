import pytest
from pathlib import Path
from app.agents.tools import (
    build_list_available_skills_tool,
    build_read_skill_instructions_tool,
)


@pytest.fixture
def skills_dir() -> Path:
    return Path(__file__).resolve().parents[5] / "skills"


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
