from __future__ import annotations

import ast
from pathlib import Path

import pytest

from engineering_page_sections.bending_page_context import (
    BendingCaseSnapshot,
    build_bending_page_snapshot,
    resolve_bending_view_state,
)


ROOT = Path(__file__).resolve().parents[1]


def _case(sign: str, *, has_case: bool = True, demand: float = 100.0):
    return BendingCaseSnapshot(
        moment_sign=sign,
        has_case=has_case,
        uls_demand_kNm=demand,
        sls_demand_kNm=demand * 0.7,
        reinforcement_area_mm2=500.0,
        effective_depth_mm=450.0,
        results={"phi_Mu_kNm": 150.0, "dn_mm": 75.0},
    )


def test_view_state_accepts_only_supported_current_selections() -> None:
    state = resolve_bending_view_state(
        selected_detail_view="negative",
        valid_detail_views=("positive", "negative"),
        selected_diagram_state="SLS (cracked)",
    )

    assert state.selected_detail_view == "negative"
    assert state.showing_negative is True
    assert state.selected_diagram_state == "SLS (cracked)"


def test_view_state_falls_back_without_changing_engineering_inputs() -> None:
    state = resolve_bending_view_state(
        selected_detail_view="stale-view",
        valid_detail_views=("negative",),
        selected_diagram_state="stale-state",
    )

    assert state.selected_detail_view == "negative"
    assert state.selected_diagram_state == "ULS"


def test_page_snapshot_selects_the_available_active_case() -> None:
    snapshot = build_bending_page_snapshot(
        engineering_state={"b": 250.0},
        check_pack={"rows": ("row",)},
        authoritative_bending={"phi_Mu_kNm": 150.0},
        authoritative_ductility={"status": "PASS"},
        section_layout={"width": 250.0},
        positive_case=_case("positive", demand=100.0),
        negative_case=_case("negative", demand=120.0),
        selected_detail_view="negative",
        valid_detail_views=("positive", "negative"),
        selected_diagram_state="ULS",
    )

    assert snapshot.active_case.moment_sign == "negative"
    assert snapshot.active_case.uls_demand_kNm == pytest.approx(120.0)


def test_page_snapshot_does_not_return_an_unavailable_negative_case() -> None:
    snapshot = build_bending_page_snapshot(
        engineering_state={},
        check_pack={},
        authoritative_bending={},
        authoritative_ductility={},
        section_layout=None,
        positive_case=_case("positive", demand=90.0),
        negative_case=_case("negative", has_case=False, demand=120.0),
        selected_detail_view="negative",
        valid_detail_views=("positive",),
        selected_diagram_state="ULS",
    )

    assert snapshot.active_case.moment_sign == "positive"
    assert snapshot.active_case.uls_demand_kNm == pytest.approx(90.0)


def test_snapshot_mappings_are_detached_and_read_only() -> None:
    source = {"phi_Mu_kNm": 150.0}
    case = BendingCaseSnapshot(
        moment_sign="positive",
        has_case=True,
        uls_demand_kNm=100.0,
        sls_demand_kNm=70.0,
        reinforcement_area_mm2=500.0,
        effective_depth_mm=450.0,
        results=source,
    )
    source["phi_Mu_kNm"] = 999.0

    assert case.results["phi_Mu_kNm"] == pytest.approx(150.0)
    with pytest.raises(TypeError):
        case.results["phi_Mu_kNm"] = 200.0
    assert case.mutable_results()["phi_Mu_kNm"] == pytest.approx(150.0)


def test_context_contract_has_no_streamlit_or_solver_dependency() -> None:
    source = (
        ROOT / "engineering_page_sections" / "bending_page_context.py"
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
    assert "bending_core" not in imported_roots
    assert "calculations" not in imported_roots


def test_runtime_routes_shared_case_selection_through_page_snapshot() -> None:
    source = (ROOT / "bending_page_runtime.py").read_text(encoding="utf-8")

    assert "bending_page_snapshot = build_bending_page_snapshot(" in source
    assert (
        "initial_mu_uls = bending_page_snapshot.active_case.uls_demand_kNm"
        in source
    )
    assert "detail_view = bending_page_snapshot.view.selected_detail_view" in source
    assert (
        "Mu_sls_active = bending_page_snapshot.negative_case.sls_demand_kNm"
        in source
    )
