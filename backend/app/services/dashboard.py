"""Dashboard figure contract shared by the frontend designer, persistence and delivery.

The frontend designer writes ``__PLOTLY_FIGURE_<i>__`` tokens where charts belong. The
build step swaps each token for a reference element pointing at the figure JSON on disk,
and delivery inlines each reference as a ``Plotly.newPlot`` call. The token, the reference
format and its parser live here together so the three steps cannot drift apart.
"""

import asyncio
import json
import logging
import re
from html import escape as escape_html
from html import unescape as unescape_html
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

PLOTLY_FIGURE_TOKEN_TEMPLATE = "__PLOTLY_FIGURE_{index}__"
PLOTLY_FIGURE_TOKEN = re.compile(
    re.escape(PLOTLY_FIGURE_TOKEN_TEMPLATE).replace(re.escape("{index}"), r"(\d+)")
)

FIGURE_FILENAME_TEMPLATE = "fig_{index}.json"

_REFERENCE_RE = re.compile(
    r"(?P<div><div\b"
    r'(?=[^>]*\bid=["\']plotly-(?P<index>\d+)["\'])'
    r'(?=[^>]*\bdata-plotly-figure=["\'](?P<reference>[^"\']+)["\'])'
    r"[^>]*></div>)",
)
_REFERENCE_ATTRIBUTE_RE = re.compile(r'\sdata-plotly-figure=["\'][^"\']+["\']')


def figure_filename(index: int) -> str:
    return FIGURE_FILENAME_TEMPLATE.format(index=index)


def render_figure_reference(index: int, reference: str) -> str:
    safe_reference = escape_html(reference, quote=True)
    return f'<div id="plotly-{index}" data-plotly-figure="{safe_reference}"></div>'


def inject_figure_references(html: str, charts: list) -> str:
    """Replace each chart token with a reference to that chart's saved figure file.

    The token index is the chart's position in ``charts``.
    """

    def repl(match: re.Match) -> str:
        idx = int(match.group(1))
        if idx < 0 or idx >= len(charts):
            logger.warning(
                "frontend_designer_invalid_figure_token index=%d chart_count=%d",
                idx,
                len(charts),
            )
            return ""
        chart = charts[idx]
        if not isinstance(chart, dict):
            return ""

        figure_path = chart.get("figure") or ""
        figure_reference = Path(str(figure_path)).name
        if not figure_reference:
            logger.warning("chart %s has no saved figure reference", idx)
            return ""

        return render_figure_reference(idx, figure_reference)

    return PLOTLY_FIGURE_TOKEN.sub(repl, html)


async def save_dashboard_html(
    session_id: UUID,
    dashboard_html: str,
    storage_root: Path,
) -> Path:
    """Persist a rendered dashboard under the session directory and return its path.

    Runs after the analyst graph, keeping graph nodes free of file I/O
    (see the profiler pattern in ``profiling.py``).
    """
    session_dir = storage_root / "sessions" / str(session_id)
    dashboard_path = session_dir / "dashboard.html"
    await asyncio.to_thread(_write_dashboard, dashboard_path, dashboard_html)
    return dashboard_path


def _write_dashboard(dashboard_path: Path, dashboard_html: str) -> None:
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(dashboard_html, encoding="utf-8")


def materialize_dashboard_html(dashboard_html: str, figures_dir: Path) -> str:
    """Inline saved Plotly figures into a dashboard for delivery to the browser.

    The persisted dashboard holds only reference elements, so Plotly JSON never enters an
    LLM prompt or the stored HTML. This returns a browser-facing copy where each reference
    is replaced by a script that calls ``Plotly.newPlot`` with the figure loaded from
    ``figures_dir``. The input HTML is not modified.
    """
    figures_root = Path(figures_dir).resolve()

    def replace_reference(match: re.Match[str]) -> str:
        index = match.group("index")
        reference = unescape_html(match.group("reference"))
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
        div = _REFERENCE_ATTRIBUTE_RE.sub("", match.group("div"), count=1)
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

    return _REFERENCE_RE.sub(replace_reference, dashboard_html)


async def load_dashboard_for_delivery(dashboard_path: Path, figures_dir: Path) -> str:
    """Read a persisted dashboard and materialize it for delivery to the browser.

    The stored file keeps its reference-based form; only the returned copy is inlined.
    """
    return await asyncio.to_thread(
        _read_dashboard_for_delivery, dashboard_path, figures_dir
    )


def _read_dashboard_for_delivery(dashboard_path: Path, figures_dir: Path) -> str:
    dashboard_html = dashboard_path.read_text(encoding="utf-8")
    return materialize_dashboard_html(dashboard_html, figures_dir)
