from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from engineering_page_sections.bending_checks_context import (
    BendingChecksSnapshot,
    build_bending_checks_snapshot,
)
from engineering_page_sections.bending_minimum_strength_checks_view import (
    render_bending_minimum_strength_checks,
)
from engineering_page_sections.bending_page_context import (
    BendingCaseSnapshot,
    build_bending_page_snapshot,
)
from engineering_page_sections.bending_sls_checks_view import (
    render_bending_sls_checks,
)
from engineering_page_sections.bending_uls_checks_view import (
    render_bending_uls_checks,
)


ROOT = Path(__file__).resolve().parents[1]


def _page_snapshot(*, selected: str):
    return build_bending_page_snapshot(
        engineering_state={},
        check_pack={},
        authoritative_bending={},
        authoritative_ductility={},
        section_layout=None,
        positive_case=BendingCaseSnapshot(
            moment_sign="positive",
            has_case=True,
            uls_demand_kNm=100.0,
            sls_demand_kNm=70.0,
            reinforcement_area_mm2=500.0,
            effective_depth_mm=420.0,
            results={
                "phi_Mu_kNm": 150.0,
                "util": 0.666,
                "ku": 0.12,
                "dn_mm": 50.4,
                "d_mm": 420.0,
                "positive_only": "kept",
            },
        ),
        negative_case=BendingCaseSnapshot(
            moment_sign="negative",
            has_case=True,
            uls_demand_kNm=80.0,
            sls_demand_kNm=55.0,
            reinforcement_area_mm2=300.0,
            effective_depth_mm=390.0,
            results={
                "phi_Mu_kNm": 120.0,
                "util": 0.75,
                "ku": 0.10,
                "dn_mm": 39.0,
                "gamma": 0.8,
                "d_mm": 390.0,
                "negative_only": "not-merged-by-legacy-projection",
            },
        ),
        selected_detail_view=selected,
        valid_detail_views=("positive", "negative"),
        selected_diagram_state="ULS",
    )


def _checks(selected: str) -> BendingChecksSnapshot:
    return build_bending_checks_snapshot(
        page_snapshot=_page_snapshot(selected=selected),
        base_results={
            "phi_Mu_cap": 140.0,
            "Mu_util": 0.7,
            "ku": 0.11,
            "c": 46.0,
            "gamma": 0.75,
            "base_only": "kept",
        },
        width_mm=250.0,
        overall_depth_mm=450.0,
        concrete_strength_mpa=40.0,
        steel_yield_strength_mpa=500.0,
        concrete_modulus_mpa=30_000.0,
        steel_modulus_mpa=200_000.0,
        positive_effective_depth_mm=410.0,
    )


def test_positive_check_projection_preserves_legacy_active_case_values() -> None:
    checks = _checks("positive")

    assert checks.uls.moment_sign == "positive"
    assert checks.uls.reinforcement_area_mm2 == pytest.approx(500.0)
    assert checks.uls.effective_depth_mm == pytest.approx(410.0)
    assert checks.uls.demand_kNm == pytest.approx(100.0)
    assert checks.sls.demand_kNm == pytest.approx(70.0)
    assert checks.uls.results["phi_Mu_cap"] == pytest.approx(150.0)
    assert checks.uls.results["Mu_util"] == pytest.approx(0.666)
    assert checks.uls.results["c"] == pytest.approx(50.4)
    assert checks.uls.results["d"] == pytest.approx(420.0)
    assert checks.uls.results["base_only"] == "kept"
    assert checks.uls.results["positive_only"] == "kept"


def test_negative_check_projection_preserves_legacy_lever_arm_projection() -> None:
    checks = _checks("negative")

    assert checks.uls.moment_sign == "negative"
    assert checks.uls.reinforcement_area_mm2 == pytest.approx(300.0)
    assert checks.uls.effective_depth_mm == pytest.approx(390.0)
    assert checks.uls.demand_kNm == pytest.approx(80.0)
    assert checks.sls.demand_kNm == pytest.approx(55.0)
    assert checks.uls.results["phi_Mu_cap"] == pytest.approx(120.0)
    assert checks.uls.results["Mu_util"] == pytest.approx(0.75)
    assert checks.uls.results["c"] == pytest.approx(39.0)
    assert checks.uls.results["a"] == pytest.approx(31.2)
    assert checks.uls.results["z"] == pytest.approx(374.4)
    assert checks.uls.results["d"] == pytest.approx(390.0)
    assert checks.uls.results["base_only"] == "kept"
    assert "negative_only" not in checks.uls.results


def test_all_check_tabs_share_one_detached_active_result_revision() -> None:
    checks = _checks("positive")

    assert dict(checks.uls.results) == dict(checks.sls.results)
    assert dict(checks.uls.results) == dict(checks.minimum_strength.results)
    with pytest.raises(TypeError):
        checks.uls.results["phi_Mu_cap"] = 999.0

    detached = checks.uls.mutable_results()
    detached["phi_Mu_cap"] = 999.0
    assert checks.uls.results["phi_Mu_cap"] == pytest.approx(150.0)


def test_check_view_boundaries_forward_typed_inputs_to_legacy_renderers(
    monkeypatch,
) -> None:
    calls: dict[str, tuple[tuple, dict]] = {}
    legacy = ModuleType("bending_tabs")

    def record(name):
        def _inner(*args, **kwargs):
            calls[name] = (args, kwargs)

        return _inner

    legacy.render_uls_tab = record("uls")
    legacy.render_sls_tab = record("sls")
    legacy.render_min_strength_tab = record("minimum")
    monkeypatch.setitem(sys.modules, "bending_tabs", legacy)
    checks = _checks("positive")

    render_bending_uls_checks(checks.uls)
    render_bending_sls_checks(checks.sls)
    render_bending_minimum_strength_checks(checks.minimum_strength)

    uls_args, uls_kwargs = calls["uls"]
    assert uls_args[1:] == pytest.approx(
        (250.0, 450.0, 40.0, 500.0, 500.0, 410.0)
    )
    assert uls_kwargs == {
        "summary_mode": False,
        "Mu_star_override": 100.0,
        "moment_sign": "positive",
    }
    sls_args, sls_kwargs = calls["sls"]
    assert sls_args[1:] == pytest.approx(
        (250.0, 450.0, 410.0, 500.0, 30_000.0, 200_000.0, 70.0)
    )
    assert sls_kwargs == {"summary_mode": False, "moment_sign": "positive"}
    minimum_args, minimum_kwargs = calls["minimum"]
    assert minimum_args[1:] == pytest.approx(
        (250.0, 450.0, 40.0, 500.0, 500.0)
    )
    assert minimum_kwargs == {"summary_mode": False}


def test_runtime_uses_one_checks_snapshot_and_no_legacy_dom_reorder() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "checks_snapshot = build_bending_checks_snapshot(" in runtime
    assert "render_bending_checks(st_module=st, checks=checks_snapshot)" in runtime
    assert "from bending_tabs import" not in runtime
    assert "Check 2 — Strain compatibility" not in runtime
    assert "streamlit.components.v1" not in runtime


def test_each_check_boundary_has_one_legacy_renderer_owner() -> None:
    files = {
        "bending_uls_checks_view.py": "render_uls_tab",
        "bending_sls_checks_view.py": "render_sls_tab",
        "bending_minimum_strength_checks_view.py": "render_min_strength_tab",
    }
    for filename, renderer in files.items():
        source = (
            ROOT / "engineering_page_sections" / filename
        ).read_text(encoding="utf-8")
        assert source.count(f"from bending_tabs import {renderer}") == 1
        assert source.count(f"{renderer}(") == 1


def test_checks_coordinator_is_the_only_calculation_tab_layout_owner() -> None:
    runtime = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")
    coordinator = (
        ROOT / "engineering_page_sections" / "bending_checks.py"
    ).read_text(encoding="utf-8")

    assert 'scope_id="bending-calculation-checks"' not in runtime
    assert 'scope_id="bending-calculation-checks"' in coordinator
    assert "Bending design checks" not in runtime
    assert "Bending design checks" in coordinator
    assert 'data-testid="bending-calculation-ready"' in coordinator
