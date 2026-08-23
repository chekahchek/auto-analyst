from pathlib import Path

from langchain_core.tools import tool

SUBMIT_TOOL_NAME = "submit_hypotheses_evidence"


def build_submit_hypotheses_evidence_tool():
    @tool
    def submit_hypotheses_evidence(hypotheses_evidence: dict) -> dict:
        """Submit the final structured hypotheses and evidence from your analysis.

        Call this tool when you are ready to submit your final answer.
        The dictionary must contain a 'hypotheses' key with supporting evidence.
        """
        return hypotheses_evidence

    return submit_hypotheses_evidence


def build_read_dashboard_html_tool():
    @tool
    def read_dashboard_html(file_path: str) -> str:
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

    return read_dashboard_html
