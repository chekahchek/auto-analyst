import asyncio
import json
import logging
import sys
import tempfile
import traceback
from pathlib import Path
import uuid

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.agents.analyst.nodes import build_analyst_graph, storyteller_node
from app.agents.analyst.states import (
    AnalystState,
    DatasetProfile,
    HypothesesEvidence,
    StorytellerOutput,
)
from app.config import Settings


logging.basicConfig(handlers=[logging.NullHandler()], force=True)
logger = logging.getLogger(__name__)

SKILLS_DIR = BACKEND_DIR.parent / "skills"
EVAL_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EVAL_DATASET_PATH = EVAL_FIXTURES_DIR / "eval_data.csv"
settings = Settings.from_ini()
logger.debug("Loaded settings: %s", settings)


def _resolve_backend_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else BACKEND_DIR / path


def get_initial_state(
    *,
    messages: list[BaseMessage] | None = None,
    profile: DatasetProfile | None = None,
    hypotheses_evidence: HypothesesEvidence | None = None,
    max_llm_calls: int = 10,
    figures_dir: Path | None = None,
) -> AnalystState:
    return AnalystState(
        dataset_path=str(EVAL_DATASET_PATH),
        figures_dir=str(figures_dir or EVAL_FIXTURES_DIR),
        messages=messages if messages is not None else [],
        profile=profile if profile is not None else {"data_type": "general"},
        hypotheses_evidence=hypotheses_evidence,
        narrative=None,
        dashboard_path=None,
        dashboard_html=None,
        critic_score=None,
        critic_feedback=None,
        iteration_count=0,
        llm_calls=0,
        max_llm_calls=max_llm_calls,
    )

def get_eval_model(model_name: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        api_key=settings.api_key,
        base_url=settings.api_base_url,
        reasoning_effort=settings.reasoning_effort or None,
        default_headers={"X-Opencode-Session": str(uuid.uuid4())}
    )


def _figure_file_status(evidence: dict, figures_dir: Path) -> list[dict]:
    statuses = []
    figures_root = figures_dir.resolve()
    for chart in evidence.get("charts", []):
        if not isinstance(chart, dict):
            statuses.append(
                {"name": "", "exists": False, "inside_figures_dir": False}
            )
            continue

        figure_path = Path(str(chart.get("figure", "")))
        try:
            inside_figures_dir = figure_path.resolve().is_relative_to(figures_root)
        except (OSError, RuntimeError):
            inside_figures_dir = False
        statuses.append(
            {
                "name": figure_path.name,
                "exists": figure_path.is_file(),
                "inside_figures_dir": inside_figures_dir,
            }
        )
    return statuses


def _load_hypotheses_evidence(path: Path) -> dict:
    with path.open(encoding="utf-8") as fixture:
        evidence = json.load(fixture)
    if not isinstance(evidence, dict):
        raise ValueError("hypotheses_evidence fixture must be a JSON object")
    return evidence


async def run_analyst(prompt, variables):
    if not EVAL_DATASET_PATH.is_file():
        return {"error": f"dataset_path not found: {EVAL_DATASET_PATH}"}

    data_type = variables.get("data_type", "general")
    model_name = variables.get("model", settings.model)
    max_llm_calls = 20
    model = get_eval_model(model_name)
    logger.debug(model_name)

    with tempfile.TemporaryDirectory(
        dir=EVAL_FIXTURES_DIR, prefix=".analyst-eval-"
    ) as temp_dir:
        figures_dir = Path(temp_dir)
        initial_state = get_initial_state(
            messages=[HumanMessage(content=str(prompt))],
            profile={"data_type": data_type},
            max_llm_calls=max_llm_calls,
            figures_dir=figures_dir,
        )

        graph = build_analyst_graph(
            SKILLS_DIR,
            model,
            interrupt_after=["parse"],
        )
        result = await graph.ainvoke(initial_state)
        evidence = result.get("hypotheses_evidence")
        figure_files = (
            _figure_file_status(evidence, figures_dir)
            if isinstance(evidence, dict)
            else []
        )
        return {
            "hypotheses_evidence": evidence,
            "llm_calls": result.get("llm_calls"),
            "figure_files": figure_files,
        }


async def run_storyteller(variables):
    fixture_path = _resolve_backend_path(str(variables["input_fixture"]))
    model_name = variables.get("model", settings.model)

    if not fixture_path.is_file():
        return {"error": f"input_fixture not found: {fixture_path}"}

    hypotheses_evidence = _load_hypotheses_evidence(fixture_path)
    model = get_eval_model(model_name).with_structured_output(StorytellerOutput)

    state = get_initial_state(
        messages=[],
        profile={"data_type": "panel"},
        hypotheses_evidence=hypotheses_evidence,
        max_llm_calls=1,
    )
    result = storyteller_node(state, model, SKILLS_DIR)
    return {
        "narrative": result["narrative"],
        "source_insight_count": len(hypotheses_evidence.get("insights", [])),
        "source_chart_count": len(hypotheses_evidence.get("charts", [])),
    }


async def call_api(prompt, options, context):
    del options
    variables = context["vars"]
    stage = variables.get("stage")

    try:
        if stage == "analyst":
            result = await run_analyst(prompt, variables)
        elif stage == "storyteller":
            result = await run_storyteller(variables)
        else:
            result = {"error": f"Unsupported eval stage: {stage}"}
        return {"output": json.dumps(result)}
    except Exception as exc:
        logger.error("%s eval failed: %s", stage, exc)
        logger.debug(traceback.format_exc())
        return {
            "output": json.dumps(
                {"error": str(exc), "traceback": traceback.format_exc()}
            )
        }


def call_api_sync(prompt, options, context):
    return asyncio.run(call_api(prompt, options, context))
