import json
import logging
from functools import partial
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.agents.analyst.prompts import (
    ANALYST_SYSTEM_PROMPT_TEMPLATE,
    FOLLOW_UP_CONTEXT_TEMPLATE,
    OUTPUT_FORMAT_INSTRUCTIONS,
    STORYTELLER_PROMPT_TEMPLATE,
    STORYTELLER_SKILL_ID,
)
from app.agents.analyst.states import AnalystState, Narrative
from app.agents.analyst.tools import (
    SUBMIT_TOOL_NAME,
    build_read_dashboard_html_tool,
    build_submit_hypotheses_evidence_tool,
)
from app.agents.common_tools import (
    build_execute_python_script_tool,
    build_list_available_skills_tool,
    build_read_skill_instructions_tool,
)

logger = logging.getLogger(__name__)


def _format_data_type(data_type) -> str:
    if isinstance(data_type, list):
        return ", ".join(str(dt) for dt in data_type)
    return str(data_type or "unknown")


def form_analyst_system_prompt(state: AnalystState) -> str:
    system_prompt = ANALYST_SYSTEM_PROMPT_TEMPLATE.format(
        dataset_path=state["dataset_path"],
        data_type=_format_data_type(state.get("profile", {}).get("data_type")),
    )

    sections = []
    if state.get("hypotheses_evidence"):
        sections.append(
            "Hypotheses and evidence:\n"
            + json.dumps(state["hypotheses_evidence"], indent=2)
        )
    if state.get("narrative"):
        sections.append("Narrative:\n" + json.dumps(state["narrative"], indent=2))
    if state.get("dashboard_path"):
        sections.append(
            "There is an existing dashboard HTML from a previous analysis. "
            f"It is saved at: {state['dashboard_path']}. "
            "You can read its contents with the `read_dashboard_html` tool, "
            "passing the dashboard path above."
        )

    if len(sections) > 0:
        follow_up_context = FOLLOW_UP_CONTEXT_TEMPLATE.format(
            context="\n\n".join(sections)
        )
        return f"{system_prompt}\n\n{follow_up_context}"
    else:
        return system_prompt


def analyst_node(
    state: AnalystState,
    model: BaseChatModel,
) -> dict:
    """Invoke the analyst LLM with dataset context and category prefixed as system prompt."""

    system_prompt = form_analyst_system_prompt(state)
    all_messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = model.invoke(all_messages)

    logger.debug(
        "analyst_response content=%r tool_calls=%s",
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


def parse_analyst_output_node(state: AnalystState) -> dict:
    """Extract the submitted hypotheses_evidence from the final tool call."""
    last = state["messages"][-1]
    for tool_call in getattr(last, "tool_calls", []):
        if tool_call.get("name") == SUBMIT_TOOL_NAME:
            return {"hypotheses_evidence": tool_call.get("args", {})}
    raise ValueError("No valid submit_hypotheses_evidence tool call found")


def should_continue(state: AnalystState) -> str:
    """Route to the tool node while the analyst is still analysing, or to parse/END otherwise."""
    last_message = state["messages"][-1]
    tool_names = {tc.get("name") for tc in getattr(last_message, "tool_calls", [])}

    # Budget control: stop even if the LLM is mid-tool-call.
    if state["llm_calls"] >= state["max_llm_calls"]:
        return END

    # The analyst is ready to submit its final insights.
    if SUBMIT_TOOL_NAME in tool_names:
        return "parse"

    # The analyst requested further tools.
    if tool_names:
        return "analyst_tools"

    # Conversational reply, no analysis needed.
    return END


def storyteller_node(
    state: AnalystState,
    model: BaseChatModel,
    skills_dir: Path,
) -> dict:
    """Generate a structured narrative from the analyst's hypotheses and evidence."""
    read_skill_instructions = build_read_skill_instructions_tool(skills_dir)
    skill_instructions = read_skill_instructions.invoke(
        {"skill_name": STORYTELLER_SKILL_ID}
    )
    system_prompt = STORYTELLER_PROMPT_TEMPLATE.format(
        skill_instructions=skill_instructions
    )
    hypotheses_evidence = json.dumps(state["hypotheses_evidence"], indent=2)

    all_messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=hypotheses_evidence),
    ]
    narrative = model.invoke(all_messages)
    return {"narrative": narrative}


def build_analyst_graph(
    skills_dir: Path,
    model: BaseChatModel,
) -> CompiledStateGraph:
    """Build and compile the analyst LangGraph."""
    list_available_skills = build_list_available_skills_tool(skills_dir)
    read_skill_instructions = build_read_skill_instructions_tool(
        skills_dir,
        output_format_instructions=OUTPUT_FORMAT_INSTRUCTIONS,
    )
    execute_python_script = build_execute_python_script_tool()
    read_dashboard_html = build_read_dashboard_html_tool()

    tools = [
        list_available_skills,
        read_skill_instructions,
        execute_python_script,
        read_dashboard_html,
    ]
    tool_node = ToolNode(tools)
    bound_model = model.bind_tools([*tools, build_submit_hypotheses_evidence_tool()])

    analyst_node_fn = partial(analyst_node, model=bound_model)
    storyteller_node_fn = partial(
        storyteller_node,
        model=model.with_structured_output(Narrative),
        skills_dir=skills_dir,
    )

    workflow = StateGraph(AnalystState)

    workflow.add_node("analyst", analyst_node_fn)
    workflow.add_node("analyst_tools", tool_node)
    workflow.add_node("parse", parse_analyst_output_node)
    workflow.add_node("storyteller", storyteller_node_fn)

    workflow.add_edge(START, "analyst")
    workflow.add_conditional_edges(
        "analyst",
        should_continue,
        {"analyst_tools": "analyst_tools", "parse": "parse", END: END},
    )
    workflow.add_edge("analyst_tools", "analyst")
    workflow.add_edge("parse", "storyteller")
    workflow.add_edge("storyteller", END)

    return workflow.compile()
