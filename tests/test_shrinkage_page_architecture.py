from __future__ import annotations

from pathlib import Path

import pytest

from application.contracts.concrete_crack_shrinkage import ShrinkageMethod
from application.page_module_registry import CALCULATION_PAGE_MODULES
from engineering_page_sections.shrinkage_checks_context import (
    ShrinkageChecksSnapshot,
)
from engineering_page_sections.shrinkage_page_context import (
    ShrinkageInputValues,
    build_shrinkage_page_snapshot,
)
from reporting.shrinkage_report_projection import (
    build_shrinkage_report_projection,
)


ROOT = Path(__file__).resolve().parents[1]


def _inputs() -> ShrinkageInputValues:
    return ShrinkageInputValues(
        method=ShrinkageMethod.EXISTING_AS3600.value,
        width_mm=300.0,
        depth_mm=600.0,
        concrete_strength_mpa=40.0,
        faces_exposed="Beam – three faces exposed",
        environment="Temperate inland environment",
        time_days=365.0,
        relative_humidity_percent=51.0,
        cement_class="S",
        drying_start_age_days=7.0,
    )


def test_shrinkage_registry_uses_the_thin_page_shell() -> None:
    spec = CALCULATION_PAGE_MODULES["shrinkage"]
    assert spec.module_name == "shrinkage_page"
    assert spec.renderer_name == "render_shrinkage"


def test_shrinkage_snapshot_detaches_and_freezes_mappings() -> None:
    engineering = {"b": 300.0}
    diagram = {"span_m": 6.0}
    summary = {"eps_cs_total": 0.0005}
    snapshot = build_shrinkage_page_snapshot(
        engineering_state=engineering,
        diagram_state=diagram,
        summary_values=summary,
        published_results={"eps_cs_total": 0.0005},
        inputs=_inputs(),
    )

    engineering["b"] = 900.0
    diagram["span_m"] = 99.0
    summary["eps_cs_total"] = 9.0
    assert snapshot.engineering_state["b"] == 300.0
    assert snapshot.diagram_state["span_m"] == 6.0
    assert snapshot.summary_values["eps_cs_total"] == 0.0005
    with pytest.raises(TypeError):
        snapshot.engineering_state["b"] = 400.0  # type: ignore[index]


def test_shrinkage_runtime_delegates_all_owned_page_sections() -> None:
    source = (ROOT / "shrinkage_page_runtime.py").read_text(encoding="utf-8")
    assert "ShrinkagePageShell.reserve_title(st)" in source
    assert "ShrinkagePageShell.reserve_visualisation(st)" in source
    assert "render_shrinkage_summary(" in source
    assert "render_shrinkage_inputs(" in source
    assert "render_shrinkage_visualisation(" in source
    assert "render_shrinkage_checks(" in source
    assert "build_shrinkage_page_snapshot(" in source


def test_extracted_sections_do_not_own_engineering_or_publication() -> None:
    for relative in (
        "engineering_page_sections/shrinkage_inputs.py",
        "engineering_page_sections/shrinkage_visualisation.py",
        "engineering_page_sections/shrinkage_summary.py",
        "engineering_page_sections/shrinkage_page_shell.py",
        "engineering_page_sections/shrinkage_checks.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "update_results(" not in source, relative
        assert "current_authoritative_family(" not in source, relative
        assert "compute_shrinkage_results(" not in source, relative
        assert "st.session_state" not in source, relative

    checks = (
        ROOT / "engineering_page_sections" / "shrinkage_checks.py"
    ).read_text(encoding="utf-8")
    assert "from calculations" not in checks
    assert "get_param(" not in checks


def test_legacy_shrinkage_facade_preserves_page_and_crack_consumers() -> None:
    facade = (ROOT / "shrinkage.py").read_text(encoding="utf-8")
    crack = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")
    assert "from shrinkage_page import" in facade
    assert "streamlit" not in facade
    assert "compute_shrinkage_components_for_crack_control" in facade
    assert "from shrinkage import" in crack
    assert len(facade.splitlines()) < 35


def test_report_projection_preserves_values_and_method_metadata() -> None:
    projection = build_shrinkage_report_projection(
        {
            "eps_cs_total": 0.00051,
            "eps_cs_total_micro": 510.0,
            "eps_cse": 0.00011,
            "eps_csd_t": 0.00040,
            "th_shrinkage": 200.0,
            "k1_shrinkage": 0.8,
        },
        method=ShrinkageMethod.EC2_C766.value,
        reference="CIRIA C766",
        warnings=("test warning",),
    )

    assert projection.result_updates() == {
        "eps_cs_total": 0.00051,
        "eps_cs_total_micro": 510.0,
        "eps_cse": 0.00011,
        "eps_csd_t": 0.00040,
        "th_shrinkage": 200.0,
        "k1_shrinkage": 0.8,
    }
    assert projection.method_update() == {
        "method": ShrinkageMethod.EC2_C766.value,
        "reference": "CIRIA C766",
        "warnings": ["test warning"],
    }
    source = (
        ROOT / "reporting" / "shrinkage_report_projection.py"
    ).read_text(encoding="utf-8")
    assert "streamlit" not in source
    assert "session_state" not in source


def test_checks_snapshot_is_frozen_and_supports_both_method_branches() -> None:
    snapshot = ShrinkageChecksSnapshot(
        method=ShrinkageMethod.EXISTING_AS3600.value,
        method_result=None,
        width_mm=300.0,
        depth_mm=600.0,
        gross_area_mm2=180000.0,
        faces_exposed="Beam – three faces exposed",
        exposed_perimeter_mm=1200.0,
        notional_thickness_raw_mm=300.0,
        notional_thickness_table_mm=400,
        concrete_strength_mpa=40.0,
        concrete_strength_table_mpa=40.0,
        environment="Temperate inland environment",
        environment_short_label="Temperate inland",
        time_days=365.0,
        k1=0.8,
        eps_cse=0.0001,
        eps_cse_final=0.0001,
        eps_csd_final=0.0005,
        eps_csd_t=0.0004,
        eps_cs_total=0.0005,
    )
    assert snapshot.eps_cs_total == pytest.approx(0.0005)
    with pytest.raises((AttributeError, TypeError)):
        snapshot.k1 = 9.0  # type: ignore[misc]


def test_runtime_keeps_as3600_and_ec2_authoritative_branches_separate() -> None:
    source = (ROOT / "shrinkage_page_runtime.py").read_text(encoding="utf-8")
    assert "current_authoritative_family(st.session_state, \"shrinkage\")" in source
    assert "if inputs.method == ShrinkageMethod.EXISTING_AS3600.value" in source
    assert "else dict(fallback)" in source
    assert "calculate_ec2_c766_shrinkage(" in source
    assert "eps_csd_final = method_result.nominal_drying_shrinkage" in source
