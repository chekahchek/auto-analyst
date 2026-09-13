import json
from pathlib import Path


def get_assert(output, context):
    try:
        result = json.loads(output)
    except json.JSONDecodeError as exc:
        return {"pass": False, "score": 0.0, "reason": f"Invalid JSON: {exc}"}

    if result.get("error"):
        return {
            "pass": False,
            "score": 0.0,
            "reason": f"Provider failed: {result['error']}",
        }

    evidence = result.get("hypotheses_evidence")
    failures = []
    if not isinstance(evidence, dict):
        failures.append("hypotheses_evidence is not an object")
        evidence = {}

    insights = evidence.get("insights")
    if not isinstance(insights, list) or not all(
        isinstance(insight, str) and insight.strip() for insight in insights
    ):
        failures.append("insights must be a non-empty list of strings")
        insights = []

    variables = context["vars"]
    min_insights = int(variables.get("min_insights", 1))
    if len(insights) < min_insights:
        failures.append(f"expected at least {min_insights} insights, got {len(insights)}")

    charts = evidence.get("charts")
    if not isinstance(charts, list):
        failures.append("charts must be a list")
        charts = []

    min_charts = int(variables.get("min_charts", 0))
    if len(charts) < min_charts:
        failures.append(f"expected at least {min_charts} charts, got {len(charts)}")

    figure_files = result.get("figure_files", [])
    for chart_index, chart in enumerate(charts):
        if not isinstance(chart, dict):
            failures.append(f"chart {chart_index} is not an object")
            continue

        missing_fields = {
            field
            for field in ("title", "insight_index", "description", "figure")
            if field not in chart
            or chart[field] is None
            or (isinstance(chart[field], str) and not chart[field].strip())
        }
        if missing_fields:
            failures.append(
                f"chart {chart_index} missing fields: {sorted(missing_fields)}"
            )

        insight_index = chart.get("insight_index")
        if not isinstance(insight_index, int) or not 0 <= insight_index < len(insights):
            failures.append(f"chart {chart_index} has an invalid insight_index")

        figure = chart.get("figure")
        if not isinstance(figure, str) or not Path(figure).is_absolute():
            failures.append(f"chart {chart_index} figure must be an absolute path")
        elif not figure.endswith(".json"):
            failures.append(f"chart {chart_index} figure must be a JSON file")

        if chart_index >= len(figure_files):
            failures.append(f"chart {chart_index} has no figure-file status")
        else:
            status = figure_files[chart_index]
            if not status.get("exists"):
                failures.append(f"chart {chart_index} figure file does not exist")
            if not status.get("inside_figures_dir"):
                failures.append(f"chart {chart_index} is outside figures_dir")

    passed = not failures
    return {
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "reason": "Analyst output passed contract and content checks"
        if passed
        else "; ".join(failures),
    }
