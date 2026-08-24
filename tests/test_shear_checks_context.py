from __future__ import annotations

import ast
from pathlib import Path

import pytest

from engineering_page_sections.shear_checks_context import (
    build_shear_checks_snapshot,
)
from engineering_page_sections.shear_page_context import (
    build_shear_page_snapshot,
)
from shear_calculation_runtime import ShearResults


ROOT = Path(__file__).resolve().parents[1]


def _page_snapshot():
    return build_shear_page_snapshot(
        engineering_state={"b": 250.0},
        check_pack={"rows": ()},
        published_results={"phi_Vu_cap": 180.0, "revision": "beam-7"},
        section_layout=None,
        actions_mode="manual",
    )


def _results() -> ShearResults:
    return ShearResults(
        b_used=250.0, D_used=300.0, A_cp=75_000.0, u_c=1_100.0,
        Ao=67_500.0, uh=990.0, A_oh=60_750.0, Tcr_kNm=10.7,
        torsion_required=False, torsion_required_limit=2.0,
        Vt_eq_kN=0.0, V_eq=120.0, b_v=250.0, d_v=255.0,
        Asv=157.1, f_syv=500.0, eps_x=0.0004, term_M=10.0,
        sqrt_inner=20.0, numerator=30.0, k_v=0.2,
        theta_v_deg=31.0, theta_v_rad=0.541052,
        sqrt_fc_limited=6.3249, Vuc_kN=80.0, Vus_kN=160.0,
        Vu_total_kN=240.0, phi_Vu=180.0, shear_ok=True,
        Vu_max_kN=400.0, LHS=0.3, RHS=0.8, web_ok=True,
    )


def _checks():
    return build_shear_checks_snapshot(
        page_snapshot=_page_snapshot(),
        calc_bundle={
            "live_state": {"b": 250.0, "Vu": 120.0},
            "actions_used": {"Vu": 120.0, "Tu": 0.0},
            "results": _results(),
            "phi": 0.75,
            "k_d": 0.5,
            "use_general_kv": True,
        },
        method="General epsilon-x method",
    )


def test_all_check_families_share_one_detached_authoritative_revision() -> None:
    checks = _checks()

    assert dict(checks.torsion_dimensions.results) == dict(checks.mcft_strength.results)
    assert dict(checks.torsion_dimensions.results) == dict(checks.reinforcement.results)
    assert checks.mcft_strength.results["phi_Vu"] == pytest.approx(180.0)
    assert checks.reinforcement.published_results["revision"] == "beam-7"
    assert checks.torsion_dimensions.phi == pytest.approx(0.75)
    assert checks.torsion_dimensions.duct_factor == pytest.approx(0.5)
    assert checks.torsion_dimensions.use_general_kv is True


def test_check_mappings_are_read_only_and_mutable_copy_is_detached() -> None:
    checks = _checks()

    with pytest.raises(TypeError):
        checks.mcft_strength.results["phi_Vu"] = 999.0
    mutable = checks.mcft_strength.mutable_results()
    mutable["phi_Vu"] = 999.0
    assert checks.mcft_strength.results["phi_Vu"] == pytest.approx(180.0)


def test_checks_context_has_no_streamlit_or_solver_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "shear_checks_context.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        str(node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert "streamlit" not in imported_roots
    assert "shear_core" not in imported_roots
    assert "shear_calculation_runtime" not in imported_roots
    assert "calculations" not in imported_roots


def test_runtime_builds_one_checks_snapshot_for_all_check_tabs() -> None:
    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8")

    assert "shear_checks_snapshot = build_shear_checks_snapshot(" in source
    assert "shear_checks_snapshot.torsion_dimensions.live_state" in source
    assert "shear_checks_snapshot.torsion_dimensions.phi" in source
    assert "shear_checks_snapshot.mcft_strength.use_general_kv" in source
