from pathlib import Path
from uuid import uuid4

import pytest

from app.services.analyst import materialize_dashboard_html, save_dashboard_html


async def test_save_dashboard_html(tmp_path: Path):
    session_id = uuid4()
    html = "<html><body>dashboard</body></html>"

    dashboard_path = await save_dashboard_html(session_id, html, tmp_path)

    assert dashboard_path == (
        tmp_path / "sessions" / str(session_id) / "dashboard.html"
    )
    assert dashboard_path.read_text(encoding="utf-8") == html


async def test_save_dashboard_html_reuses_session_dir(tmp_path: Path):
    session_id = uuid4()

    first = await save_dashboard_html(session_id, "v1", tmp_path)
    second = await save_dashboard_html(session_id, "v2", tmp_path)

    assert first == second
    assert first.read_text(encoding="utf-8") == "v2"
    assert len(list((tmp_path / "sessions").iterdir())) == 1


def test_materialize_dashboard_html_inlines_figures(tmp_path: Path):
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    (figures_dir / "fig_0.json").write_text(
        '{"data":[{"type":"bar","name":"<safe>"}],'
        '"layout":{"title":{"text":"Sales & margin"}}}',
        encoding="utf-8",
    )
    html = (
        '<html><body><div class="plotly-figure">'
        '<div id="plotly-0" data-plotly-figure="fig_0.json"></div>'
        "</div></body></html>"
    )

    materialized = materialize_dashboard_html(html, figures_dir)

    assert 'data-plotly-figure="fig_0.json"' not in materialized
    assert 'Plotly.newPlot("plotly-0"' in materialized
    assert '"type":"bar"' in materialized
    assert "\\u003csafe\\u003e" in materialized
    assert "fig_0.json" not in materialized
    assert materialize_dashboard_html(materialized, figures_dir) == materialized


def test_materialize_dashboard_html_requires_figure_file(tmp_path: Path):
    html = '<div id="plotly-0" data-plotly-figure="fig_0.json"></div>'

    with pytest.raises(FileNotFoundError):
        materialize_dashboard_html(html, tmp_path)
