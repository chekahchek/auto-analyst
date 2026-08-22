import json
import logging
from functools import partial
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agents.profiler.prompts import (
    PROFILER_SKILL_ID,
    RETRY_PROMPT,
    SYSTEM_PROMPT_TEMPLATE,
)
from app.agents.profiler.states import ProfilerState
from app.agents.tools import (
    build_execute_python_script_tool,
    build_read_skill_instructions_tool,
)

logger = logging.getLogger(__name__)


def profiler_node(
    state: ProfilerState,
    model: BaseChatModel,
    skills_dir: Path,
) -> dict:
    """Invoke the LLM with the profile-data skill prepended as a system prompt."""
    read_skill_instructions = build_read_skill_instructions_tool(skills_dir)
    skill_instructions = read_skill_instructions.invoke(
        {"skill_name": PROFILER_SKILL_ID}
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(skill_instructions=skill_instructions)

    if state["messages"]:
        last_msg = state["messages"][-1]
        if isinstance(last_msg, ToolMessage):
            logger.info(
                "tool_result length=%d preview=%r",
                len(last_msg.content or ""),
                (last_msg.content or "")[:1000],
            )

    all_messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = model.invoke(all_messages)

    logger.debug(
        "ai_message content=%r tool_calls=%s",
        response.content,
        [
            {"name": tc.get("name"), "args": tc.get("args")}
            for tc in getattr(response, "tool_calls", [])
        ],
    )

    return {
        "messages": [response],
        "llm_calls": state["llm_calls"] + 1,
    }


def retry_node(_state: ProfilerState) -> dict:
    """Append a reminder when the last answer was not valid JSON."""
    return {"messages": [SystemMessage(content=RETRY_PROMPT)]}


def should_continue(state: ProfilerState) -> str:
    """Route to the tool node if the LLM requested a tool call, or to retry/END otherwise."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    if tool_calls and state["llm_calls"] < state["max_llm_calls"]:
        return "tools"

    if not tool_calls:
        try:
            json.loads(last_message.content)
            return END
        except (json.JSONDecodeError, TypeError):
            if state["llm_calls"] < state["max_llm_calls"]:
                logger.debug("invalid_json response, retrying")
                return "retry"
            logger.debug("invalid_json response but max calls reached, ending graph")
            return END

    return END


def build_profiler_graph(
    skills_dir: Path,
    model: BaseChatModel,
) -> CompiledStateGraph:
    """Build and compile the profiler LangGraph."""

    execute_python_script = build_execute_python_script_tool()
    tools = [execute_python_script]
    tool_node = ToolNode(tools)
    bound_model = model.bind_tools(tools)

    profile_node = partial(
        profiler_node,
        model=bound_model,
        skills_dir=skills_dir,
    )

    workflow = StateGraph(ProfilerState)

    workflow.add_node("profile", profile_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("retry", retry_node)

    workflow.add_edge(START, "profile")
    workflow.add_conditional_edges(
        "profile",
        should_continue,
        {"tools": "tools", "retry": "retry", END: END},
    )
    workflow.add_edge("tools", "profile")
    workflow.add_edge("retry", "profile")

    return workflow.compile()
