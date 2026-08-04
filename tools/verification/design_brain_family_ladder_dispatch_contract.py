"""Focused contract check for family-first ladder dispatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.family_ladder_dispatch import (  # noqa: E402
    LADDER_METHOD_BY_FAMILY,
    resolve_family_ladder_dispatch,
)


SEARCH_FAMILIES = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL",
    "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
    "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN",
    "SERVICEABILITY_GOVERNS",
)


def _classification(family_id: str) -> dict:
    return {
        "selected_family_id": family_id,
        "classification_passed": True,
        "classification_hash": f"proof:{family_id}",
    }


def main() -> int:
    decisions = {
        family_id: resolve_family_ladder_dispatch(_classification(family_id)).to_dict()
        for family_id in SEARCH_FAMILIES
    }
    alias = resolve_family_ladder_dispatch(
        _classification("COMBINED_OVERDESIGN_GOVERNS")
    ).to_dict()
    terminal = resolve_family_ladder_dispatch(
        _classification("TARGET_BAND_REACHED")
    ).to_dict()
    unclassified = resolve_family_ladder_dispatch({}).to_dict()
    direct_source = (
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "family_ladder_guidance.py"
    ).read_text(encoding="utf-8", errors="replace")
    guidance_source = (
        ROOT / "inputs_page_modules" / "guidance_compute.py"
    ).read_text(encoding="utf-8", errors="replace")

    checks = {
        "all_required_search_families_have_contract": all(
            family_id in LADDER_METHOD_BY_FAMILY for family_id in SEARCH_FAMILIES
        ),
        "all_required_search_families_dispatch_first": all(
            decision["should_run_family_ladder"] for decision in decisions.values()
        ),
        "all_required_search_families_forbid_legacy_fallback": all(
            not decision["legacy_fallback_allowed"] for decision in decisions.values()
        ),
        "combined_overdesign_alias_normalised": (
            alias["normalised_family_id"] == "COMBINED_OVERDESIGN"
            and alias["should_run_family_ladder"]
        ),
        "terminal_family_skips_search_without_legacy_fallback": (
            terminal["terminal_family"]
            and not terminal["should_run_family_ladder"]
            and not terminal["legacy_fallback_allowed"]
        ),
        "unclassified_state_does_not_silently_run_legacy_search": (
            not unclassified["should_run_family_ladder"]
            and not unclassified["legacy_fallback_allowed"]
            and unclassified["legacy_fallback_reason"]
            == "family_classification_not_proven"
        ),
        "classified_family_exhaustion_cannot_enter_broad_fallback": (
            'not dispatch_decision.get("legacy_fallback_allowed")'
            in direct_source
            and '"family_ladder_exhausted_without_legacy_fallback": True'
            in direct_source
        ),
        "classified_family_exhaustion_skips_generic_solver": (
            "generic_one_click_solver_skipped_by_family_owner"
            in guidance_source
            and "run_bounded_one_click_solver" not in guidance_source
            and "_solve_one_click_candidate(" not in guidance_source
        ),
    }
    report = {
        "schema": "design_brain_family_ladder_dispatch_contract.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "decisions": decisions,
        "combined_overdesign_alias": alias,
        "terminal": terminal,
        "unclassified": unclassified,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
