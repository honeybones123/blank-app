from __future__ import annotations

from pathlib import Path

import pytest

from application.contracts.concrete_crack_shrinkage import (
    AS5100WallCrackControlInput,
    C766CrackControlInput,
    C766EndRestraintInput,
    RestraintType,
)
from application.page_module_registry import CALCULATION_PAGE_MODULES
from calculations.concrete_crack_shrinkage_methods import (
    calculate_as5100_wall_crack_control,
    calculate_c766_crack_control,
    calculate_c766_end_restraint,
)
from engineering_page_sections.crack_checks_context import (
    CrackAs3600ChecksSnapshot,
    freeze_expanded_steps,
)
from engineering_page_sections.crack_page_context import (
    build_crack_page_snapshot,
)
from reporting.crack_report_projection import (
    project_as3600_results,
    project_as5100_wall_result,
    project_c766_end_result,
    project_c766_result,
)


ROOT = Path(__file__).resolve().parents[1]


def test_crack_registry_uses_the_thin_page_shell() -> None:
    spec = CALCULATION_PAGE_MODULES["crack"]
    assert spec.module_name == "crack_page"
    assert spec.renderer_name == "render_crack_control"


def test_crack_page_snapshot_detaches_and_freezes_mappings() -> None:
    engineering = {"sigma_sr": 120.0}
    diagram = {"span_m": 6.0}
    row = {"uid": "crk_step_1", "status": "PASS"}
    metrics = {"w_calc_mm": 0.21}
    snapshot = build_crack_page_snapshot(
        method="existing_as3600",
        engineering_state=engineering,
        diagram_state=diagram,
        summary_rows=[row],
        crack_metrics=metrics,
    )

    engineering["sigma_sr"] = 999.0
    diagram["span_m"] = 99.0
    row["status"] = "FAIL"
    metrics["w_calc_mm"] = 9.0
    assert snapshot.engineering_state["sigma_sr"] == 120.0
    assert snapshot.diagram_state["span_m"] == 6.0
    assert snapshot.summary_rows[0]["status"] == "PASS"
    assert snapshot.crack_metrics["w_calc_mm"] == pytest.approx(0.21)
    with pytest.raises(TypeError):
        snapshot.engineering_state["sigma_sr"] = 1.0  # type: ignore[index]


def test_crack_runtime_delegates_all_owned_page_sections() -> None:
    source = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")
    for call in (
        "render_crack_summary(",
        "render_as3600_inputs(",
        "render_as5100_wall_inputs(",
        "render_c766_inputs(",
        "render_as3600_crack_diagrams(",
        "render_method_crack_diagrams(",
        "render_as3600_crack_checks(",
        "render_as5100_method_checks(",
        "render_c766_method_checks(",
        "build_crack_page_snapshot(",
        "project_as3600_results(",
        "project_as5100_wall_result(",
        "project_c766_result(",
        "project_c766_end_result(",
    ):
        assert call in source


def test_c766_runtime_maps_long_term_restraint_to_authoritative_contract() -> None:
    source = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")
    assert "restraint_long_term=method_inputs.restraint_long" in source
    assert "restraint_long=method_inputs.restraint_long" not in source


def test_extracted_crack_presentation_does_not_own_engineering_or_publication() -> None:
    for relative in (
        "engineering_page_sections/crack_as3600_checks.py",
        "engineering_page_sections/crack_method_checks.py",
        "engineering_page_sections/crack_visualisation.py",
        "engineering_page_sections/crack_summary.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "update_results(" not in source, relative
        assert "current_authoritative_family(" not in source, relative
        assert "st.session_state" not in source, relative
        assert "from calculations" not in source, relative

    for relative in (
        "engineering_page_sections/crack_as3600_inputs.py",
        "engineering_page_sections/crack_method_inputs.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "update_results(" not in source, relative
        assert "from calculations" not in source, relative
        assert "calculate_as5100" not in source, relative
        assert "calculate_c766" not in source, relative


def test_as3600_checks_snapshot_and_expansion_state_are_frozen() -> None:
    expanded = {"crk_step_1": True}
    frozen = freeze_expanded_steps(expanded)
    expanded["crk_step_1"] = False
    assert frozen["crk_step_1"] is True
    with pytest.raises(TypeError):
        frozen["crk_step_1"] = False  # type: ignore[index]

    snapshot = CrackAs3600ChecksSnapshot(
        width_limit_mm=0.3,
        member_type="Primarily flexure",
        bar_diameter_mm=20.0,
        bar_spacing_mm=200.0,
        steel_stress_mpa=120.0,
        steel_yield_strength_mpa=500.0,
        table_basis="table",
        table_limit_a_mpa=180.0,
        table_limit_b_mpa=200.0,
        table_combined_limit_mpa=200.0,
        yield_limit_mpa=400.0,
        allowable_stress_mpa=200.0,
        table_utilisation=0.6,
        table_passes=True,
        effective_tension_area_mm2=20000.0,
        tension_steel_area_mm2=942.0,
        effective_reinforcement_ratio=0.0471,
        concrete_tensile_strength_mpa=3.4,
        steel_modulus_mpa=200000.0,
        concrete_modulus_mpa=30000.0,
        creep_coefficient=1.2,
        effective_modular_ratio=14.67,
        shrinkage_microstrain=500.0,
        strain_difference=0.0008,
        cover_mm=40.0,
        bond_coefficient=0.8,
        strain_distribution_factor=0.5,
        maximum_crack_spacing_mm=250.0,
        crack_width_mm=0.2,
        width_utilisation=0.667,
        width_passes=True,
        expanded_steps=frozen,
    )
    assert snapshot.crack_width_mm == pytest.approx(0.2)
    with pytest.raises((AttributeError, TypeError)):
        snapshot.crack_width_mm = 9.0  # type: ignore[misc]


def test_crack_report_projection_is_pure_and_exact() -> None:
    values = {
        "sigma_allow_table": 200.0,
        "sigma_sr": 120.0,
        "w_calc": 0.2,
        "wmax_char": 0.3,
        "passes_table": True,
        "passes_w": True,
        "crack_width": 0.2,
        "crack_sr_max_mm": 250.0,
        "crack_utilisation": 2.0 / 3.0,
    }
    projection = project_as3600_results(values)
    assert projection.result_update() == values
    source = (
        ROOT / "reporting" / "crack_report_projection.py"
    ).read_text(encoding="utf-8")
    assert "streamlit" not in source
    assert "session_state" not in source


def test_selectable_method_report_projections_preserve_authoritative_results() -> None:
    wall_result = calculate_as5100_wall_crack_control(
        AS5100WallCrackControlInput(
            wall_thickness_mm=600.0,
            provided_horizontal_area_per_face_mm2_per_m=2750.0,
            provided_vertical_spacing_mm=150.0,
        )
    )
    wall_projection = project_as5100_wall_result(wall_result).result_update()
    assert wall_projection["required_area_per_face_mm2_per_m"] == pytest.approx(
        wall_result.required_area_per_face_mm2_per_m
    )
    assert wall_projection["maximum_spacing_mm"] == pytest.approx(
        wall_result.maximum_spacing_mm
    )
    assert wall_projection["area_utilisation"] == pytest.approx(
        wall_result.area_utilisation
    )
    assert wall_projection["passes"] is wall_result.passes

    shrinkage = {
        "method": "existing_as3600",
        "autogenous_early": 0.00004,
        "autogenous_long_term": 0.00008,
        "drying_long_term": 0.00030,
    }
    c766_result = calculate_c766_crack_control(
        C766CrackControlInput(
            restraint_type=RestraintType.CONTINUOUS_EDGE,
            temperature_drop_early_c=20.0,
            temperature_change_long_term_c=10.0,
            thermal_expansion_per_c=10e-6,
            autogenous_shrinkage_early=shrinkage["autogenous_early"],
            autogenous_shrinkage_long_term=shrinkage[
                "autogenous_long_term"
            ],
            drying_shrinkage=shrinkage["drying_long_term"],
            restraint_early=0.8,
            restraint_medium=0.6,
            restraint_long_term=0.4,
            tensile_strain_capacity=90e-6,
            cover_mm=45.0,
            bar_diameter_mm=16.0,
            effective_reinforcement_ratio=0.01,
        )
    )
    c766_projection = project_c766_result(
        c766_result,
        restraint_type=RestraintType.CONTINUOUS_EDGE.value,
        shrinkage_components=shrinkage,
    ).result_update()
    assert c766_projection["restrained_strain"] == pytest.approx(
        c766_result.restrained_strain
    )
    assert c766_projection["crack_inducing_strain"] == pytest.approx(
        c766_result.crack_inducing_strain
    )
    assert c766_projection["maximum_crack_spacing_mm"] == pytest.approx(
        c766_result.maximum_crack_spacing_mm
    )
    assert c766_projection["characteristic_crack_width_mm"] == pytest.approx(
        c766_result.characteristic_crack_width_mm
    )
    assert c766_projection["drying_shrinkage"] == pytest.approx(
        shrinkage["drying_long_term"]
    )

    end_result = calculate_c766_end_restraint(
        C766EndRestraintInput(
            effective_modular_ratio=7.0,
            non_uniform_stress_coefficient_k=0.65,
            stress_distribution_coefficient_kc=1.0,
            characteristic_tensile_strength_at_cracking_mpa=2.0,
            reinforcement_modulus_mpa=200_000.0,
            reinforcement_ratio_total_to_tension_area=0.01,
            cover_mm=45.0,
            bar_diameter_mm=16.0,
            effective_reinforcement_ratio=0.01,
        )
    )
    end_projection = project_c766_end_result(
        end_result,
        restraint_type=RestraintType.END.value,
    ).result_update()
    assert end_projection["crack_inducing_strain"] == pytest.approx(
        end_result.crack_inducing_strain
    )
    assert end_projection["maximum_crack_spacing_mm"] == pytest.approx(
        end_result.maximum_crack_spacing_mm
    )
    assert end_projection["characteristic_crack_width_mm"] == pytest.approx(
        end_result.characteristic_crack_width_mm
    )


def test_runtime_keeps_three_authoritative_method_branches_and_no_legacy_paths() -> None:
    source = (ROOT / "crack_page_runtime.py").read_text(encoding="utf-8")
    assert "calculate_as5100_wall_crack_control(" in source
    assert "calculate_c766_crack_control(" in source
    assert "calculate_c766_end_restraint(" in source
    assert "compute_crack_control_values(" in source
    assert "def _render_as5100_wall_method(" not in source
    assert "def _render_c766_method(" not in source
    assert "def _render_method_summary(" not in source
    assert "bind_runtime(" not in source
    inputs_source = (
        ROOT / "engineering_page_sections" / "crack_inputs.py"
    ).read_text(encoding="utf-8")
    assert "bind_runtime(" not in inputs_source
