"""Rule-based DeepEval metrics for the profiler and analyst outputs.

Each metric reads the JSON payload stored in ``LLMTestCase.actual_output``.
It scores 1.0 when no rule is violated and 0.0 otherwise, with the
violations listed as the reason.
"""

import json
from pathlib import Path
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

CHART_REQUIRED_FIELDS = ("title", "insight_index", "description", "figure")


class RuleMetric(BaseMetric):
    def __init__(self, name: str) -> None:
        self._name = name
        self.threshold = 1.0

    @property
    def __name__(self) -> str:
        return self._name

    def violations(self, output: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    def measure(self, test_case: LLMTestCase, *args: Any, **kwargs: Any) -> float:
        problems = self.violations(json.loads(test_case.actual_output))
        self.score = 0.0 if problems else 1.0
        self.reason = "; ".join(problems) or "All checks passed"
        return self.score

    async def a_measure(
        self, test_case: LLMTestCase, *args: Any, **kwargs: Any
    ) -> float:
        return self.measure(test_case)


class ProfilerMetric(RuleMetric):
    """The profiler's data_type must mention the expected value."""

    def __init__(self, expected_value: str) -> None:
        super().__init__("Profiler data type")
        self.expected_value = expected_value

    def violations(self, output: dict[str, Any]) -> list[str]:
        data_type = output.get("data_type", [])
        candidates = [data_type] if isinstance(data_type, str) else data_type
        if any(self.expected_value in str(item) for item in candidates):
            return []
        return [
            f"Expected data_type containing '{self.expected_value}', got {data_type!r}"
        ]


class AnalystContractMetric(RuleMetric):
    """Checks the analyst's hypotheses_evidence contract and its saved figures.

    Expects ``hypotheses_evidence`` plus ``figure_files``: one status entry per
    chart, recorded while the figures directory still exists.
    """

    def __init__(self, min_insights: int = 1, min_charts: int = 0) -> None:
        super().__init__("Analyst contract")
        self.min_insights = min_insights
        self.min_charts = min_charts

    def violations(self, output: dict[str, Any]) -> list[str]:
        if output.get("error"):
            return [f"Provider failed: {output['error']}"]

        evidence = output.get("hypotheses_evidence")
        if not isinstance(evidence, dict):
            return ["hypotheses_evidence is not an object"]

        problems = []
        insights = evidence.get("insights")
        if not isinstance(insights, list) or not all(
            isinstance(insight, str) and insight.strip() for insight in insights
        ):
            problems.append("insights must be a list of non-empty strings")
            insights = []
        if len(insights) < self.min_insights:
            problems.append(
                f"expected at least {self.min_insights} insights, got {len(insights)}"
            )

        charts = evidence.get("charts")
        if not isinstance(charts, list):
            problems.append("charts must be a list")
            charts = []
        if len(charts) < self.min_charts:
            problems.append(
                f"expected at least {self.min_charts} charts, got {len(charts)}"
            )

        figure_files = output.get("figure_files", [])
        for index, chart in enumerate(charts):
            status = figure_files[index] if index < len(figure_files) else None
            problems.extend(_chart_violations(index, chart, len(insights), status))
        return problems


def _chart_violations(
    index: int,
    chart: Any,
    insight_count: int,
    figure_status: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(chart, dict):
        return [f"chart {index} is not an object"]

    problems = []
    missing = [
        field for field in CHART_REQUIRED_FIELDS if not _is_filled(chart.get(field))
    ]
    if missing:
        problems.append(f"chart {index} missing fields: {missing}")

    insight_index = chart.get("insight_index")
    if not isinstance(insight_index, int) or not 0 <= insight_index < insight_count:
        problems.append(f"chart {index} has an invalid insight_index")

    figure = chart.get("figure")
    if not isinstance(figure, str) or not Path(figure).is_absolute():
        problems.append(f"chart {index} figure must be an absolute path")
    elif not figure.endswith(".json"):
        problems.append(f"chart {index} figure must be a JSON file")

    if figure_status is None:
        problems.append(f"chart {index} has no figure-file status")
    else:
        if not figure_status.get("exists"):
            problems.append(f"chart {index} figure file does not exist")
        if not figure_status.get("inside_figures_dir"):
            problems.append(f"chart {index} is outside figures_dir")
    return problems


def _is_filled(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())
