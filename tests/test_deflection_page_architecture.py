from __future__ import annotations

from pathlib import Path

import pytest

from application.page_module_registry import CALCULATION_PAGE_MODULES
from engineering_page_sections.deflection_checks import DeflectionCheckPresentation
from engineering_page_sections.deflection_checks_context import (
    build_deflection_checks_snapshot,
)
from engineering_page_sections.deflection_page_context import (
    build_deflection_diagram_snapshot,
    build_deflection_page_snapshot,
)
from reporting.deflection_report_projection import (
    project_deflection_report_params,
)


ROOT = Path(__file__).resolve().parents[1]


def test_deflection_registry_uses_the_composition_shell() -> None:
    spec = CALCULATION_PAGE_MODULES["deflection"]
    assert spec.module_name == "deflection"
    assert spec.renderer_name == "render_deflection"


def test_deflection_page_snapshot_detaches_and_freezes_publication() -> None:
    pack = {"status": "PASS", "rows": [{"uid": "defl_ief"}]}
    row = {"uid": "defl_ief", "status": "PASS"}
    snapshot = build_deflection_page_snapshot(
        summary_pack=pack,
        summary_rows=[row],
    )

    pack["status"] = "FAIL"
    row["status"] = "FAIL"
    assert snapshot.summary_pack["status"] == "PASS"
    assert snapshot.summary_rows[0]["status"] == "PASS"
    with pytest.raises(TypeError):
        snapshot.summary_pack["status"] = "FAIL"  # type: ignore[index]


def test_deflection_diagram_snapshot_freezes_nested_reinforcement_layers() -> None:
    layers = {
        "bottom": [{"count": 3, "db": 20.0, "y_from_top_mm": 550.0}],
        "top": [{"count": 2, "db": 16.0, "y_from_top_mm": 48.0}],
    }
    resolution = {
        "multi_span": True,
        "controlling_span_idx": 1,
        "controlling_reason": "longest active span",
    }
    snapshot = build_deflection_diagram_snapshot(
        span_mm=6000.0,
        depth_mm=600.0,
        total_deflection_mm=5.2,
        support_type="Simply supported",
        continuous_end_side=None,
        support_pair=("pin", "roller"),
        support_resolution=resolution,
        reo_layers=layers,
    )

    layers["bottom"][0]["count"] = 99
    resolution["controlling_span_idx"] = 9
    assert snapshot.reo_layers["bottom"][0]["count"] == 3
    assert snapshot.controlling_span_idx == 1
    with pytest.raises(TypeError):
        snapshot.reo_layers["bottom"][0]["count"] = 4  # type: ignore[index]


def test_prepared_deflection_check_is_immutable() -> None:
    check = DeflectionCheckPresentation(
        step_id="defl_short",
        title="Short-term deflection",
        summary_md="summary",
        calc_md="calculation",
        status_kind="pass",
    )
    assert check.step_id == "defl_short"
    with pytest.raises((AttributeError, TypeError)):
        check.title = "changed"  # type: ignore[misc]


def test_deflection_checks_snapshot_deep_freezes_display_inputs() -> None:
    source = {"derived": {"w_kN_per_m": 4.2}, "support_type": "Cantilever"}
    snapshot = build_deflection_checks_snapshot(source)
    source["derived"]["w_kN_per_m"] = 99.0
    assert snapshot["derived"]["w_kN_per_m"] == pytest.approx(4.2)
    with pytest.raises(TypeError):
        snapshot["derived"]["w_kN_per_m"] = 1.0  # type: ignore[index]


def test_deflection_report_projection_is_pure_detached_and_exact() -> None:
    params = {"Ief": 1.2e10, "delta_total": 4.1, "support_type": "Cantilever"}
    projection = project_deflection_report_params(params)
    params["delta_total"] = 99.0
    assert projection.report_params() == {
        "Ief": 1.2e10,
        "delta_total": 4.1,
        "support_type": "Cantilever",
    }
    source = (
        ROOT / "reporting" / "deflection_report_projection.py"
    ).read_text(encoding="utf-8")
    assert "streamlit" not in source
    assert "session_state" not in source

    core_source = (ROOT / "deflection_core.py").read_text(encoding="utf-8")
    assert "project_deflection_report_params(" in core_source
    assert "build_deflection_report(report_projection.report_params())" in core_source


def test_deflection_runtime_delegates_owned_presentation_sections() -> None:
    source = (ROOT / "deflection_page_runtime.py").read_text(encoding="utf-8")
    for call in (
        "build_deflection_page_snapshot(",
        "render_deflection_summary(",
        "build_deflection_diagram_snapshot(",
        "render_deflection_diagram(",
        "build_deflection_checks_snapshot(",
        "render_deflection_checks(",
    ):
        assert call in source
    assert "bind_runtime(" not in source
    assert "render_expandable_step(" not in source
    assert "build_deflected_beam_plotly(" not in source


def test_extracted_deflection_presentation_does_not_own_engineering_state() -> None:
    for relative in (
        "engineering_page_sections/deflection_summary.py",
        "engineering_page_sections/deflection_visualisation.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "update_results(" not in source, relative
        assert "st.session_state" not in source, relative
        assert "from calculations" not in source, relative

    checks_source = (
        ROOT / "engineering_page_sections" / "deflection_checks.py"
    ).read_text(encoding="utf-8")
    assert "update_results(" not in checks_source
    assert "st.session_state" not in checks_source


def test_deflection_runtime_has_no_runtime_global_mutation_bridge() -> None:
    for relative in (
        "deflection_page_runtime.py",
        "engineering_page_sections/deflection_inputs.py",
        "engineering_page_sections/deflection_diagrams.py",
        "engineering_page_sections/deflection_support.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "bind_runtime(" not in source, relative
        assert "globals().update(" not in source, relative
