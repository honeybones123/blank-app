from __future__ import annotations

from pathlib import Path

from application.page_module_registry import CALCULATION_PAGE_MODULES


ROOT = Path(__file__).resolve().parents[1]


PAGE_CONTRACTS = {
    "creep": {
        "registry": ("creep_page", "render_creep"),
        "runtime": "creep_page_runtime.py",
        "delegates": (
            "build_creep_page_snapshot(",
            "render_creep_summary(",
            "render_creep_inputs(",
            "render_creep_visualisation(",
            "render_creep_checks(",
        ),
        "presentation": (
            "engineering_page_sections/creep_summary.py",
            "engineering_page_sections/creep_visualisation.py",
            "engineering_page_sections/creep_checks.py",
        ),
        "report": "reporting/creep_report_projection.py",
    },
    "shrinkage": {
        "registry": ("shrinkage_page", "render_shrinkage"),
        "runtime": "shrinkage_page_runtime.py",
        "delegates": (
            "build_shrinkage_page_snapshot(",
            "render_shrinkage_summary(",
            "render_shrinkage_inputs(",
            "render_shrinkage_visualisation(",
            "render_shrinkage_checks(",
        ),
        "presentation": (
            "engineering_page_sections/shrinkage_summary.py",
            "engineering_page_sections/shrinkage_visualisation.py",
            "engineering_page_sections/shrinkage_checks.py",
        ),
        "report": "reporting/shrinkage_report_projection.py",
    },
    "crack": {
        "registry": ("crack_page", "render_crack_control"),
        "runtime": "crack_page_runtime.py",
        "delegates": (
            "build_crack_page_snapshot(",
            "render_crack_summary(",
            "render_as3600_crack_diagrams(",
            "render_method_crack_diagrams(",
            "render_as3600_crack_checks(",
            "render_as5100_method_checks(",
            "render_c766_method_checks(",
        ),
        "presentation": (
            "engineering_page_sections/crack_summary.py",
            "engineering_page_sections/crack_visualisation.py",
            "engineering_page_sections/crack_as3600_checks.py",
            "engineering_page_sections/crack_method_checks.py",
        ),
        "report": "reporting/crack_report_projection.py",
    },
    "deflection": {
        "registry": ("deflection", "render_deflection"),
        "runtime": "deflection_page_runtime.py",
        "delegates": (
            "build_deflection_page_snapshot(",
            "render_deflection_summary(",
            "build_deflection_diagram_snapshot(",
            "render_deflection_diagram(",
            "build_deflection_checks_snapshot(",
            "render_deflection_checks(",
        ),
        "presentation": (
            "engineering_page_sections/deflection_summary.py",
            "engineering_page_sections/deflection_visualisation.py",
            "engineering_page_sections/deflection_checks.py",
        ),
        "report": "reporting/deflection_report_projection.py",
    },
}


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_documented_contract_names_every_verified_page_and_boundary() -> None:
    contract = _source("docs/CALCULATION_PAGE_MODULE_CONTRACT.md")
    for heading in ("Creep", "Shrinkage", "Crack Control", "Deflection"):
        assert f"**{heading}**" in contract
    for boundary in (
        "Composition shell",
        "Runtime coordinator",
        "Immutable page/check snapshots",
        "Summary owner",
        "Compact-input owner",
        "Visualisation owner",
        "Calculation-check owner",
        "Report projection",
    ):
        assert f"**{boundary}**" in contract


def test_all_four_routes_use_the_verified_composition_shells() -> None:
    for slug, contract in PAGE_CONTRACTS.items():
        module_name, renderer_name = contract["registry"]
        spec = CALCULATION_PAGE_MODULES[slug]
        assert (spec.module_name, spec.renderer_name) == (
            module_name,
            renderer_name,
        )


def test_each_runtime_delegates_every_owned_presentation_boundary() -> None:
    for contract in PAGE_CONTRACTS.values():
        runtime = _source(contract["runtime"])
        for call in contract["delegates"]:
            assert call in runtime, (contract["runtime"], call)


def test_extracted_presentation_has_no_state_or_publication_owner() -> None:
    forbidden = (
        "st.session_state",
        "update_results(",
        "current_authoritative_family(",
        "bind_runtime(",
        "globals().update(",
    )
    for contract in PAGE_CONTRACTS.values():
        for relative in contract["presentation"]:
            source = _source(relative)
            for token in forbidden:
                assert token not in source, (relative, token)


def test_report_projections_are_pure_and_streamlit_free() -> None:
    for contract in PAGE_CONTRACTS.values():
        source = _source(contract["report"])
        assert "streamlit" not in source, contract["report"]
        assert "session_state" not in source, contract["report"]
        assert "update_results(" not in source, contract["report"]


def test_no_modularised_runtime_uses_a_global_mutation_bridge() -> None:
    for contract in PAGE_CONTRACTS.values():
        source = _source(contract["runtime"])
        assert "bind_runtime(" not in source, contract["runtime"]
        assert "globals().update(" not in source, contract["runtime"]


def test_crack_control_preserves_distinct_method_renderers() -> None:
    runtime = _source("crack_page_runtime.py")
    for call in (
        "render_as3600_inputs(",
        "render_as5100_wall_inputs(",
        "render_c766_inputs(",
        "project_as3600_results(",
        "project_as5100_wall_result(",
        "project_c766_result(",
        "project_c766_end_result(",
    ):
        assert call in runtime


def test_deflection_presentation_keeps_serviceability_authority_in_runtime() -> None:
    runtime = _source("deflection_page_runtime.py")
    checks = _source("engineering_page_sections/deflection_checks.py")
    visualisation = _source(
        "engineering_page_sections/deflection_visualisation.py"
    )
    assert "calc_deflection_as3600(" in runtime
    assert "compute_and_store_multispan_deflection_metrics(" in runtime
    assert "calc_deflection_as3600(" not in checks
    assert "compute_and_store_multispan_deflection_metrics(" not in checks
    assert "calc_deflection_as3600(" not in visualisation
