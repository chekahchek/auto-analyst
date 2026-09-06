from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

SUBMIT_TOOL_NAME = "submit_hypotheses_evidence"
UPDATE_DASHBOARD_TOOL_NAME = "update_dashboard_html"


def build_submit_hypotheses_evidence_tool():
    @tool
    def submit_hypotheses_evidence(hypotheses_evidence: dict) -> dict:
        """Submit the final structured hypotheses and evidence from your analysis.

        Call this tool when you are ready to submit your final answer. The dictionary must
        contain 'insights' (list of strings) and 'charts' (list of chart objects). Each chart's
        'figure' must be the absolute path to a saved Plotly JSON file, not inline JSON.
        """
        return hypotheses_evidence

    return submit_hypotheses_evidence


def build_read_dashboard_tool():
    @tool
    def read_dashboard(file_path: str) -> str:
        """Reads the dashboard HTML file at the given path and returns its contents.

        Use this when a dashboard already exists for this conversation (as informed by the
        system prompt) and you need to inspect what was previously shown, e.g. to answer a
        follow-up question or avoid regenerating charts already displayed.
        """
        dashboard_path = Path(file_path)
        if not dashboard_path.is_file():
            return (
                f"No dashboard HTML found at '{file_path}'. "
                "There is no dashboard available to read."
            )
        return dashboard_path.read_text(encoding="utf-8")

    return read_dashboard


def build_read_figure_tool():
    @tool
    def read_figure(index: int, state: Annotated[dict, InjectedState]) -> str:
        """Reads a single Plotly figure JSON file from the figures directory.

        Use this to inspect a chart's figure so you can modify it with
        `execute_python_script`. `index` is the zero-based index of the chart in
        the narrative's `charts` array.
        """
        figures_dir = Path(state["figures_dir"])
        figure_path = Path(figures_dir) / f"fig_{index}.json"
        if not figure_path.is_file():
            return (
                f"No figure file found at '{figure_path}'. "
                "There is no figure to read for this index."
            )
        return figure_path.read_text(encoding="utf-8")

    return read_figure


def build_update_dashboard_html_tool():
    @tool
    def update_dashboard_html(dashboard_html: str) -> str:
        """Submit the edited HTML as the new dashboard artifact.

        Call this tool when the user asked you to modify the existing dashboard and you
        have the final, complete HTML document ready. Pass the whole HTML, not a diff.
        """
        return dashboard_html

    return update_dashboard_html
