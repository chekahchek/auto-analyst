import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams
from deepeval.tracing import observe, update_current_trace
from langchain_core.messages import BaseMessage, HumanMessage

from app.agents.analyst.nodes import (
    build_analyst_graph,
    storyteller_node,
    with_storyteller_output,
)
from app.agents.analyst.states import AnalystState
from app.agents.profiler.nodes import build_profiler_graph
from app.dependencies import get_model, get_settings
from app.services.profiling import run_profiler_graph
from metrics import AnalystContractMetric, ProfilerMetric
from llm_model import JudgeModel

DATA_TYPE = "panel"
SKILLS_DIR = get_settings().skills_dir
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DATASET_PATH = FIXTURES_DIR / "eval_data.csv"
EVIDENCE_PATH = FIXTURES_DIR / "hypotheses_evidence.json"

pytestmark = [
    pytest.mark.deepeval,
    pytest.mark.skipif(
        os.environ.get("RUN_DEEPEVAL") != "1",
        reason="Set RUN_DEEPEVAL=1 (or use `make eval`) to run the LLM evals.",
    ),
]


def analyst_state(
    *,
    figures_dir: Path,
    messages: list[BaseMessage],
    hypotheses_evidence: dict[str, Any] | None = None,
    max_llm_calls: int,
) -> AnalystState:
    return AnalystState(
        dataset_path=str(DATASET_PATH),
        figures_dir=str(figures_dir),
        messages=messages,
        profile={"data_type": DATA_TYPE},
        hypotheses_evidence=hypotheses_evidence,
        narrative=None,
        dashboard_path=None,
        dashboard_html=None,
        critic_score=None,
        critic_feedback=None,
        iteration_count=0,
        artifact_action=None,
        llm_calls=0,
        max_llm_calls=max_llm_calls,
    )


def test_profiler_tags_dataset_as_panel() -> None:
    """Test that the profiler tags the dataset as a panel."""
    _run_profiler()

    assert_test(
        golden=Golden(input=f"Profile {DATASET_PATH.name}"),
        metrics=[ProfilerMetric(expected_value=DATA_TYPE)],
    )


def test_analyst_submits_grounded_insights_and_charts() -> None:
    analyst_question = (
        "Generate insights for this dataset. It is a simple dataset so do not need "
        "to overthink. Just keep it very simple."
    )
    _run_analyst(analyst_question)

    assert_test(
        golden=Golden(input=analyst_question),
        metrics=[AnalystContractMetric(min_insights=2, min_charts=1)],
    )


def test_storyteller_narrative_quality() -> None:
    STORYTELLER_CRITERIA = """
    Evaluate the response as a data storyteller.
    Use the supplied source insights and chart descriptions as the factual reference.
    Ignore chart file paths.

    Assess the candidate based on these criteria:
    - Narrative flow: it has a clear central question or hook, progresses logically
    from context through evidence to a takeaway, and does not read like a
    disconnected list of slides.
    - Meaning and implications: it explains what the findings mean and why they
    matter, rather than merely repeating numbers or chart titles. Conclusions,
    decisions, or cautions should follow from the evidence where appropriate.
    - Grounding: its important claims are supported by the supplied insights and
    charts, without material contradictions or invented key findings.

    A coherent, useful, mostly grounded story should meet the 0.5 pass threshold
    (roughly 5/10 on DeepEval's judge scale), even if it omits optional findings or
    is not especially polished. A story that lacks a sensible progression, does not
    interpret the findings, or materially misstates the evidence should fall below
    that threshold.
    """
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    _run_storyteller(evidence)

    assert_test(
        golden=Golden(input="Tell the story behind the supplied insights and charts."),
        metrics=[
            GEval(
                name="Storyteller narrative quality",
                criteria=STORYTELLER_CRITERIA,
                evaluation_params=[
                    SingleTurnParams.ACTUAL_OUTPUT,
                    SingleTurnParams.CONTEXT,
                ],
                threshold=0.5,
                model=JudgeModel(
                    chat_model=get_model(), model_name=get_settings().model
                ),
            )
        ],
    )


### ======================================== EXECUTION ============================================ ###
@observe(name="profiler")
def _run_profiler() -> None:
    graph = build_profiler_graph(SKILLS_DIR, get_model()).with_config(
        callbacks=[CallbackHandler()]
    )
    profile = asyncio.run(
        run_profiler_graph(
            storage_path=str(DATASET_PATH),
            graph=graph,
            max_llm_calls=10,
        )
    )
    update_current_trace(output=json.dumps(profile))


@observe(name="analyst")
def _run_analyst(question: str) -> None:
    result = asyncio.run(_analyze_dataset(question))
    update_current_trace(output=json.dumps(result))


@observe(name="storyteller")
def _run_storyteller(evidence: dict[str, Any]) -> None:
    model = with_storyteller_output(get_model()).with_config(
        callbacks=[CallbackHandler()]
    )
    state = analyst_state(
        figures_dir=FIXTURES_DIR,
        messages=[],
        hypotheses_evidence=evidence,
        max_llm_calls=1,
    )
    narrative = storyteller_node(state, model, SKILLS_DIR)["narrative"]
    update_current_trace(
        context=[json.dumps(evidence, ensure_ascii=False, indent=2)],
        output=json.dumps(narrative, ensure_ascii=False, indent=2),
    )


async def _analyze_dataset(question: str) -> dict[str, Any]:
    # Stop after `parse` so the storyteller and frontend designer are not run.
    graph = build_analyst_graph(
        SKILLS_DIR,
        get_model(),
        interrupt_after=["parse"],
    )
    with tempfile.TemporaryDirectory(prefix="deepeval-analyst-") as tmp:
        figures_dir = Path(tmp)
        state = analyst_state(
            figures_dir=figures_dir,
            messages=[HumanMessage(content=question)],
            max_llm_calls=20,
        )
        final = await graph.ainvoke(state, config={"callbacks": [CallbackHandler()]})
        evidence = final.get("hypotheses_evidence")
        return {
            "hypotheses_evidence": evidence,
            "llm_calls": final.get("llm_calls"),
            # Recorded here because the figures directory is deleted on exit.
            "figure_files": _figure_file_status(evidence, figures_dir),
        }


def _figure_file_status(
    evidence: dict[str, Any] | None, figures_dir: Path
) -> list[dict[str, Any]]:
    if not isinstance(evidence, dict):
        return []

    root = figures_dir.resolve()
    statuses = []
    for chart in evidence.get("charts", []):
        if not isinstance(chart, dict):
            statuses.append({"name": "", "exists": False, "inside_figures_dir": False})
            continue
        figure = Path(str(chart.get("figure", "")))
        statuses.append(
            {
                "name": figure.name,
                "exists": figure.is_file(),
                "inside_figures_dir": figure.resolve().is_relative_to(root),
            }
        )
    return statuses
