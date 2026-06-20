import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.profiler.prompts import (
    PROFILER_SKILL_ID,
    RETRY_PROMPT,
    SYSTEM_PROMPT_TEMPLATE,
)
from app.agents.profiler.states import ProfilerState


def call_profiler(
    state: ProfilerState,
    model: BaseChatModel,
    read_skill_instructions,
) -> dict:
    """Invoke the LLM with the profile-data skill prepended as a system prompt."""
    skill_instructions = read_skill_instructions.invoke(
        {"skill_name": PROFILER_SKILL_ID}
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(skill_instructions=skill_instructions)

    all_messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = model.invoke(all_messages)

    return {
        "messages": [response],
        "llm_calls": state["llm_calls"] + 1,
    }


def retry_node(_state: ProfilerState) -> dict:
    """Append a reminder when the last answer was not valid JSON."""
    return {"messages": [HumanMessage(content=RETRY_PROMPT)]}


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
                return "retry"
            return END

    return END


def build_profiler_graph(agent_node, tool_node: ToolNode, retry_node):
    """Build and compile the profiler LangGraph."""
    workflow = StateGraph(ProfilerState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("retry", retry_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "retry": "retry", END: END},
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("retry", "agent")

    return workflow.compile()
