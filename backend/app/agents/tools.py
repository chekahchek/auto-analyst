import re
from typing import Any

import yaml
from langchain_core.tools import tool


def parse_skill_frontmatter(content: str) -> dict[str, Any]:
    """Parse the YAML frontmatter block of a SKILL.md into a dict.

    Returns an empty dict when there is no valid frontmatter block.
    """
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return {}
    try:
        data = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def build_list_available_skills_tool(SKILLS_DIR):
    @tool
    def list_available_skills() -> str:
        """Returns a list of all step-by-step instruction skills available, with their name and description."""
        skill_files = sorted(SKILLS_DIR.glob("**/SKILL.md"))
        if not skill_files:
            return f"No skills found under '{SKILLS_DIR}'."

        lines = []
        for path in skill_files:
            skill_id = path.parent.relative_to(SKILLS_DIR).as_posix()
            content = path.read_text(encoding="utf-8")

            frontmatter = parse_skill_frontmatter(content)
            name = str(frontmatter.get("name") or skill_id)
            description = str(frontmatter.get("description") or "")

            entry = f"- **{name}** (`{skill_id}`)"
            if description:
                entry += f": {description}"
            lines.append(entry)

        return "Available Skills:\n" + "\n".join(lines)

    return list_available_skills


def build_read_skill_instructions_tool(SKILLS_DIR):
    @tool
    def read_skill_instructions(skill_name: str) -> str:
        """Loads the full step-by-step instructions and python code template for a specific skill.
        Pass the skill_id shown in backticks from list_available_skills (e.g. 'core/profile-data')."""
        try:
            file_path = SKILLS_DIR / skill_name / "SKILL.md"
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: Skill '{skill_name}' not found."

    return read_skill_instructions


def build_execute_python_script_tool():
    @tool
    def execute_python_script(code: str) -> str:
        """Executes a block of Python code locally and returns stdout/stderr.
        Use this to run the final adapted skill script.
        """
        import sys
        import io

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = sys.stdout = io.StringIO()
        redirected_error = sys.stderr = io.StringIO()

        try:
            exec(code, {"__builtins__": __builtins__})
            stdout_result = redirected_output.getvalue()
            stderr_result = redirected_error.getvalue()

            if stderr_result:
                return f"Execution Error:\n{stderr_result}"
            return f"Execution Success. Output:\n{stdout_result}"

        except Exception as e:
            return f"Runtime Exception: {str(e)}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    return execute_python_script
