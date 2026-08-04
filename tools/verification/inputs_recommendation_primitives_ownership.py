"""Freeze direct ownership of deterministic recommendation primitives."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    owner = (
        ROOT / "inputs_application" / "recommendation_primitives.py"
    ).read_text(encoding="utf-8")
    compute = (
        ROOT / "inputs_page_modules" / "recommendation_compute.py"
    ).read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in owner
    assert "inputs_page_route_coordinators" not in owner
    assert "streamlit" not in owner
    assert "globals()" not in owner
    for name in (
        "annotate_bottom_candidate_deltas",
        "bottom_arrangement_to_shared_updates",
        "candidate_is_growth_move",
        "required_ast_for_arrangement",
        "shear_change_magnitude",
        "shear_detailing_updates_pure",
        "shortlist_smallest_successful_shear_candidates",
    ):
        assert f"{name} as " in compute, name
    print("PASS: deterministic recommendation primitives are application-owned")


if __name__ == "__main__":
    main()
