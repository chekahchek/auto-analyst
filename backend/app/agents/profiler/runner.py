import json
from functools import partial
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from app.agents.exceptions import ProfilerError
from app.agents.profiler.nodes import call_profiler, retry_node, build_profiler_graph
from app.agents.profiler.states import ProfilerState
from app.agents.tools import (
    build_execute_python_script_tool,
    build_read_skill_instructions_tool,
)


async def profile_dataset(
    storage_path: str,
    skills_dir: Path,
    model: BaseChatModel,
    max_llm_calls: int,
) -> dict[str, Any]:
    """Profile a dataset by inferring its data type(s) and business domain.

    Args:
        storage_path: Path to the uploaded CSV file.
        skills_dir: Root directory containing skill markdown files.
        model: A LangChain chat model. Will be bound with profiler tools inside this function.
        max_llm_calls: Maximum number of LLM calls allowed before aborting.

    Returns:
        A dict with ``data_type`` (list) and ``business_domain`` (str).

    Raises:
        ProfilerError: If the skill is missing or the final answer is not valid JSON.
    """
    read_skill_instructions = build_read_skill_instructions_tool(skills_dir)
    execute_python_script = build_execute_python_script_tool()

    tools = [execute_python_script]
    tool_node = ToolNode(tools)
    bound_model = model.bind_tools(tools)

    agent_node = partial(
        call_profiler,
        model=bound_model,
        read_skill_instructions=read_skill_instructions,
    )
    graph = build_profiler_graph(agent_node, tool_node, retry_node)

    initial_state = ProfilerState(
        storage_path=storage_path,
        llm_calls=0,
        max_llm_calls=max_llm_calls,
        messages=[HumanMessage(content=f"Path to my uploaded data: '{storage_path}'")],
    )

    final_state = await graph.ainvoke(initial_state)
    last_message = final_state["messages"][-1]

    try:
        return json.loads(last_message.content)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ProfilerError(
            f"Profiler did not return valid JSON. Final message: {last_message.content!r}"
        ) from exc
