from __future__ import annotations

from pathlib import Path

import pytest

from application.page_module_registry import CALCULATION_PAGE_MODULES
from engineering_page_sections.creep_page_context import (
    CreepInputValues,
    build_creep_page_snapshot,
)
from engineering_page_sections.creep_checks_context import CreepChecksSnapshot
from reporting.creep_report_projection import build_creep_report_projection


ROOT = Path(__file__).resolve().parents[1]


def test_creep_registry_uses_the_thin_page_shell() -> None:
    spec = CALCULATION_PAGE_MODULES["creep"]
    assert spec.module_name == "creep_page"
    assert spec.renderer_name == "render_creep"


def test_creep_page_snapshot_detaches_and_freezes_mappings() -> None:
    engineering = {"b": 300.0}
    summary = {"phi_cc_t": 1.2}
    published = {"creep": {"phi_cc_t": 1.2}}
    diagram = {"span_m": 6.0}
    inputs = CreepInputValues(
        width_mm=300.0,
        depth_mm=600.0,
        concrete_strength_mpa=40.0,
        concrete_modulus_mpa=32000.0,
        faces_exposed="Beam – three faces exposed",
        environment="Temperate inland environment",
        time_after_loading_days=365.0,
        age_at_loading_days=28.0,
    )
    snapshot = build_creep_page_snapshot(
        engineering_state=engineering,
        diagram_state=diagram,
        summary_values=summary,
        published_results=published,
        inputs=inputs,
    )

    engineering["b"] = 999.0
    summary["phi_cc_t"] = 9.9
    diagram["span_m"] = 99.0
    assert snapshot.engineering_state["b"] == 300.0
    assert snapshot.diagram_state["span_m"] == 6.0
    assert snapshot.summary_values["phi_cc_t"] == 1.2
    with pytest.raises(TypeError):
        snapshot.engineering_state["b"] = 400.0  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.diagram_state["span_m"] = 8.0  # type: ignore[index]


def test_creep_runtime_delegates_owned_page_sections() -> None:
    source = (ROOT / "creep_page_runtime.py").read_text(encoding="utf-8")
    assert "CreepPageShell.reserve_title(st)" in source
    assert "CreepPageShell.reserve_visualisation(st)" in source
    assert "render_creep_summary(" in source
    assert "render_creep_inputs(" in source
    assert "render_creep_visualisation(" in source
    assert "build_creep_page_snapshot(" in source


def test_creep_input_and_visual_modules_do_not_own_engineering_publication() -> None:
    for relative in (
        "engineering_page_sections/creep_inputs.py",
        "engineering_page_sections/creep_visualisation.py",
        "engineering_page_sections/creep_summary.py",
        "engineering_page_sections/creep_page_shell.py",
        "engineering_page_sections/creep_checks.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "update_results(" not in source, relative
        assert "current_authoritative_family(" not in source, relative
        assert "compute_creep_results(" not in source, relative
        assert "st.session_state" not in source, relative

    checks_source = (
        ROOT / "engineering_page_sections" / "creep_checks.py"
    ).read_text(encoding="utf-8")
    assert "from calculations" not in checks_source
    assert "get_param(" not in checks_source


def test_legacy_creep_import_is_a_small_compatibility_facade() -> None:
    source = (ROOT / "creep.py").read_text(encoding="utf-8")
    assert "from creep_page import" in source
    assert "streamlit" not in source
    assert len(source.splitlines()) < 30


def test_creep_report_projection_is_pure_and_preserves_values() -> None:
    source = {
        "phi_cc_t": 1.234,
        "phi_cc_star_table": 2.345,
        "k2_creep": 0.8,
        "k3_creep": 0.9,
        "k4_creep": 1.0,
        "k5_creep": 1.1,
        "k6_creep": 1.2,
        "eps_cc": 0.000456,
        "eps_cc_micro": 456.0,
    }
    projection = build_creep_report_projection(source)

    assert projection.result_updates(include_strain=False) == {
        "phi_cc_t": 1.234,
        "phi_cc_star_table": 2.345,
        "k2_creep": 0.8,
        "k3_creep": 0.9,
        "k4_creep": 1.0,
        "k5_creep": 1.1,
        "k6_creep": 1.2,
    }
    assert projection.result_updates(include_strain=True)["eps_cc"] == pytest.approx(
        0.000456
    )
    assert projection.result_updates(include_strain=True)[
        "eps_cc_micro"
    ] == pytest.approx(456.0)

    report_source = (
        ROOT / "reporting" / "creep_report_projection.py"
    ).read_text(encoding="utf-8")
    assert "streamlit" not in report_source
    assert "session_state" not in report_source


def test_legacy_report_registry_keeps_the_creep_compute_entrypoint() -> None:
    """PDF/report consumers can still import the established Creep facade."""

    registry_source = (
        ROOT / "reporting" / "module_registry.py"
    ).read_text(encoding="utf-8")
    facade_source = (ROOT / "creep.py").read_text(encoding="utf-8")

    assert "from creep import compute_creep_results" in registry_source
    assert "compute_creep_results" in facade_source


def test_creep_checks_snapshot_is_frozen_and_calculation_complete() -> None:
    snapshot = CreepChecksSnapshot(
        width_mm=300.0,
        depth_mm=600.0,
        gross_area_mm2=180000.0,
        faces_exposed="Beam – three faces exposed",
        exposed_perimeter_mm=1200.0,
        notional_thickness_raw_mm=300.0,
        notional_thickness_table_mm=400,
        time_after_loading_days=365.0,
        age_at_loading_days=28.0,
        concrete_strength_mpa=40.0,
        concrete_modulus_mpa=32000.0,
        environment="Temperate inland environment",
        alpha2=1.04,
        phi_cc_b=2.2,
        k2=0.8,
        k3=0.9,
        k4=1.0,
        k5=1.0,
        k6=1.0,
        phi_cc_t=1.584,
        phi_cc_star_table=2.0,
        sustained_moment_knm=100.0,
        sustained_compression_fibre="top",
        sustained_section_modulus_mm3=18_000_000.0,
        sustained_stress_mpa=5.556,
        sustained_stress_ratio=0.139,
        eps_cc=0.000275,
        eps_cc_micro=275.0,
    )

    assert snapshot.phi_cc_t == pytest.approx(1.584)
    with pytest.raises((AttributeError, TypeError)):
        snapshot.k2 = 9.0  # type: ignore[misc]
