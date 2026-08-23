import re
from typing import Any

import yaml
from langchain_core.tools import tool
import tempfile
import subprocess
import sys
from pathlib import Path


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


def build_read_skill_instructions_tool(
    SKILLS_DIR, output_format_instructions: str | None = None
):
    @tool
    def read_skill_instructions(skill_name: str) -> str:
        """Loads the full step-by-step instructions and python code template for a specific skill.
        Pass the skill_id shown in backticks from list_available_skills (e.g. 'core/profile-data')."""
        try:
            file_path = SKILLS_DIR / skill_name / "SKILL.md"
            with open(file_path, "r", encoding="utf-8") as f:
                skills_content = f.read()
            if output_format_instructions and "analytical/" in skill_name:
                skills_content += "\n\n" + output_format_instructions
            return skills_content
        except FileNotFoundError:
            return f"Error: Skill '{skill_name}' not found."

    return read_skill_instructions


def build_execute_python_script_tool():
    @tool
    def execute_python_script(code: str) -> str:
        """Executes a block of independent Python code in a subprocess and returns stdout/stderr.
        Each call is fully isolated — imports and variables must be defined inside the code block.
        i.e. If you are using pandas, you must always include `import pandas as pd` in the code block.
        even if the previous code block already imported pandas.
        """
        timeout = 120  # adjust as needed
        script_path = None

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                script_path = f.name

            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            stdout = result.stdout
            stderr = result.stderr

            if result.returncode != 0:
                return (
                    f"Execution Error (exit {result.returncode}):\n{stderr}\n{stdout}"
                )
            if stderr:
                return f"Execution Success (stderr present):\n{stderr}\n{stdout}"
            return f"Execution Success.\n{stdout}"

        except subprocess.TimeoutExpired:
            return f"Execution timed out after {timeout} seconds."
        except Exception as e:
            return f"Runtime Exception: {str(e)}"
        finally:
            if script_path:
                try:
                    Path(script_path).unlink(missing_ok=True)
                except Exception:
                    pass

    return execute_python_script
