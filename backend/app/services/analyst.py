import asyncio
import json
import logging
import re
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

_PLOTLY_REFERENCE_RE = re.compile(
    r"(?P<div><div\b"
    r'(?=[^>]*\bid=["\']plotly-(?P<index>\d+)["\'])'
    r'(?=[^>]*\bdata-plotly-figure=["\'](?P<reference>[^"\']+)["\'])'
    r"[^>]*></div>)",
)
_PLOTLY_REFERENCE_ATTRIBUTE_RE = re.compile(r'\sdata-plotly-figure=["\'][^"\']+["\']')


async def save_dashboard_html(
    session_id: UUID,
    dashboard_html: str,
    storage_path: Path,
) -> Path:
    """Persist a rendered dashboard to disk and return its path.

    Runs after the analyst graph, keeping graph nodes free of file I/O
    (see the profiler pattern in ``profiling.py``).
    """
    session_dir = storage_path / "sessions" / str(session_id)
    dashboard_path = session_dir / "dashboard.html"
    await asyncio.to_thread(_write_dashboard, dashboard_path, dashboard_html)
    return dashboard_path


def _write_dashboard(dashboard_path: Path, dashboard_html: str) -> None:
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(dashboard_html, encoding="utf-8")


def materialize_dashboard_html(dashboard_html: str, figures_dir: Path) -> str:
    """Inline saved Plotly figures into a dashboard response.

    The graph stores reference-based HTML so Plotly JSON never enters an LLM prompt
    or the persisted dashboard. This function creates the browser-facing copy by
    loading only the session's figure files and adding the corresponding Plotly
    calls. The input HTML is not modified.

    Convert the HTML that has Plotly figure references to fully inlined so that it can be
    displayed in the frontend. This is done by replaciing the <div id="plotly-{idx}"... <div>
    with a script that calls Plotly.newPlot with the figure JSON loaded from the corresponding file.
    """
    figures_root = Path(figures_dir).resolve()

    def replace_reference(match: re.Match[str]) -> str:
        index = match.group("index")
        reference = match.group("reference")
        figure_name = Path(reference)
        if (
            figure_name.is_absolute()
            or figure_name.name != reference
            or figure_name.suffix != ".json"
        ):
            raise ValueError(f"Invalid Plotly figure reference: {reference!r}")

        figure_path = (figures_root / figure_name).resolve()
        if not figure_path.is_relative_to(figures_root):
            raise ValueError(
                f"Plotly figure is outside the figures directory: {reference!r}"
            )
        if not figure_path.is_file():
            raise FileNotFoundError(f"Plotly figure not found: {figure_path}")

        figure = json.loads(figure_path.read_text(encoding="utf-8"))
        if not isinstance(figure, dict):
            raise ValueError(f"Plotly figure must be a JSON object: {figure_path}")

        # Escape HTML-sensitive characters so arbitrary chart text cannot close the
        # script element before the JSON is parsed by the browser.
        figure_json = json.dumps(figure, ensure_ascii=True, separators=(",", ":"))
        figure_json = (
            figure_json.replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )
        div = _PLOTLY_REFERENCE_ATTRIBUTE_RE.sub("", match.group("div"), count=1)
        script = (
            "<script>\n"
            "  (() => {\n"
            f"    const figure = {figure_json};\n"
            f'    Plotly.newPlot("plotly-{index}", figure.data || [], '
            "figure.layout || {}, figure.config || {});\n"
            "  })();\n"
            "</script>"
        )
        return f"{div}{script}"

    return _PLOTLY_REFERENCE_RE.sub(replace_reference, dashboard_html)
