from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.analyst.tools import build_update_dashboard_html_tool
from app.services.dashboard import (
    PLOTLY_FIGURE_TOKEN,
    PLOTLY_FIGURE_TOKEN_TEMPLATE,
    figure_filename,
    inject_figure_references,
    materialize_dashboard_html,
    render_figure_reference,
    save_dashboard_html,
)


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


@pytest.mark.parametrize("figure_name", ["fig_0.json", "sales & margin.json"])
async def test_figure_contract_round_trips_from_token_to_delivery(
    tmp_path: Path,
    figure_name: str,
):
    session_id = uuid4()
    figures_dir = tmp_path / "sessions" / str(session_id) / "figures"
    figures_dir.mkdir(parents=True)
    (figures_dir / figure_name).write_text(
        '{"data":[{"type":"bar","x":["Q1"],"y":[1]}],"layout":{"title":{"text":"Sales"}}}',
        encoding="utf-8",
    )
    token_html = (
        f"<html><body>{PLOTLY_FIGURE_TOKEN_TEMPLATE.format(index=0)}</body></html>"
    )
    charts = [{"figure": str(figures_dir / figure_name)}]

    injected = inject_figure_references(token_html, charts)
    saved_path = await save_dashboard_html(session_id, injected, tmp_path)
    delivered = materialize_dashboard_html(
        saved_path.read_text(encoding="utf-8"), figures_dir
    )

    assert render_figure_reference(0, figure_name) in injected
    assert PLOTLY_FIGURE_TOKEN.search(injected) is None
    assert 'Plotly.newPlot("plotly-0"' in delivered
    assert '"type":"bar"' in delivered
    assert "data-plotly-figure" not in delivered


def test_llm_placeholder_example_is_a_valid_reference(tmp_path: Path):
    (tmp_path / figure_filename(0)).write_text('{"data":[]}', encoding="utf-8")
    example = '<div id="plotly-0" data-plotly-figure="fig_0.json"></div>'

    assert example in build_update_dashboard_html_tool().description
    assert render_figure_reference(0, figure_filename(0)) == example
    assert 'Plotly.newPlot("plotly-0"' in materialize_dashboard_html(example, tmp_path)
