"""Regression checks for explicit Design Guide family classification."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "verification"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.family_chooser import (  # noqa: E402
    FAMILY_SELECTION_CONTRACT_VIOLATION,
    classify_family_from_raw_flags,
)


BASE_FLAGS = {
    "geometry_detailing_fail": False,
    "serviceability_fail": False,
    "bending_fail": False,
    "shear_fail": False,
    "min_bending_reo_fail": False,
    "min_shear_reo_fail": False,
    "bending_overdesigned": False,
    "shear_overdesigned": False,
    "bending_within_target_band": False,
    "shear_within_target_band": False,
    "locked_repair_blocked": False,
    "legal_repair_exists": False,
    "repair_required": False,
    "exact_stop_proven": False,
    "bending_acceptable": False,
    "shear_acceptable": False,
    "bending_not_applicable": False,
    "shear_not_applicable": False,
}


def _flags(**updates: bool) -> dict:
    out = dict(BASE_FLAGS)
    out.update(updates)
    return out


CASES = [
    {
        "case_id": "pure_shear_underdesign",
        "expected": "SHEAR_FAIL_GOVERNS",
        "flags": _flags(shear_fail=True, legal_repair_exists=True, bending_acceptable=True),
    },
    {
        "case_id": "pure_shear_overdesign",
        "expected": "SHEAR_OVERDESIGN_GOVERNS",
        "flags": _flags(shear_overdesigned=True, bending_within_target_band=True, bending_acceptable=True),
    },
    {
        "case_id": "combined_bending_shear_failure",
        "expected": "COMBINED_BENDING_SHEAR_FAIL",
        "flags": _flags(bending_fail=True, shear_fail=True, legal_repair_exists=True),
    },
    {
        "case_id": "bending_fail_shear_overdesign_mixed_owner",
        "expected": "BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS",
        "flags": _flags(
            bending_fail=True,
            shear_overdesigned=True,
            legal_repair_exists=True,
            repair_required=True,
            shear_acceptable=True,
        ),
    },
    {
        "case_id": "shear_fail_bending_overdesign_mixed_owner",
        "expected": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "flags": _flags(
            shear_fail=True,
            bending_overdesigned=True,
            legal_repair_exists=True,
            repair_required=True,
            bending_acceptable=True,
        ),
    },
    {
        "case_id": "combined_overdesign",
        "expected": "COMBINED_OVERDESIGN",
        "flags": _flags(bending_overdesigned=True, shear_overdesigned=True),
    },
    {
        "case_id": "geometry_detailing_plus_strength_failure",
        "expected": "GEOMETRY_DETAILING_GOVERNS",
        "flags": _flags(geometry_detailing_fail=True, bending_fail=True, shear_fail=True),
    },
    {
        "case_id": "geometry_detailing_only",
        "expected": "GEOMETRY_DETAILING_GOVERNS",
        "flags": _flags(geometry_detailing_fail=True),
    },
    {
        "case_id": "minimum_bending_reo_maps_to_bending_overdesign_owner",
        "expected": "BENDING_OVERDESIGN_GOVERNS",
        "flags": _flags(min_bending_reo_fail=True),
    },
    {
        "case_id": "minimum_shear_reo_maps_to_shear_overdesign_owner",
        "expected": "SHEAR_OVERDESIGN_GOVERNS",
        "flags": _flags(min_shear_reo_fail=True),
    },
    {
        "case_id": "serviceability_plus_strength_issue",
        "expected": "SERVICEABILITY_GOVERNS",
        "flags": _flags(serviceability_fail=True, bending_fail=True, shear_fail=True),
    },
    {
        "case_id": "locked_required_repair_blocked",
        "expected": "LOCKED_NO_REPAIR",
        "flags": _flags(shear_fail=True, repair_required=True, locked_repair_blocked=True, legal_repair_exists=False),
    },
    {
        "case_id": "serviceability_locked_no_repair_owned_by_serviceability",
        "expected": "SERVICEABILITY_GOVERNS",
        "flags": _flags(
            serviceability_fail=True,
            repair_required=True,
            locked_repair_blocked=True,
            legal_repair_exists=False,
            bending_acceptable=True,
            shear_acceptable=True,
        ),
    },
    {
        "case_id": "zero_match_state",
        "expected": FAMILY_SELECTION_CONTRACT_VIOLATION,
        "flags": _flags(),
        "expected_match_count": 0,
    },
    {
        "case_id": "safe_near_limit_above_cleanup_band_maps_to_target_band",
        "expected": FAMILY_SELECTION_CONTRACT_VIOLATION,
        "flags": _flags(
            bending_acceptable=True,
            shear_acceptable=True,
            bending_within_target_band=False,
            shear_within_target_band=True,
        ),
        "expected_match_count": 0,
    },
    {
        "case_id": "explicit_target_band_requires_both_applicable_domains_in_band",
        "expected": "TARGET_BAND_REACHED",
        "flags": _flags(
            bending_within_target_band=True,
            shear_within_target_band=True,
        ),
    },
    {
        "case_id": "underband_bending_with_target_shear_is_bending_overdesign_not_terminal",
        "expected": "BENDING_OVERDESIGN_GOVERNS",
        "flags": _flags(
            bending_overdesigned=True,
            bending_acceptable=True,
            shear_within_target_band=True,
            shear_acceptable=True,
        ),
    },
    {
        "case_id": "multi_match_target_and_exact_stop",
        "expected": FAMILY_SELECTION_CONTRACT_VIOLATION,
        "flags": _flags(bending_within_target_band=True, shear_within_target_band=True, exact_stop_proven=True),
        "expected_min_match_count": 2,
    },
]


def main() -> int:
    results = []
    failures: list[str] = []
    for case in CASES:
        result = classify_family_from_raw_flags(case["flags"], evidence={"case_id": case["case_id"]})
        matched = list(result.get("matched_family_ids") or [])
        selected = result.get("selected_family_id")
        case_failures: list[str] = []
        if selected != case["expected"]:
            case_failures.append(f"expected {case['expected']} got {selected}")
        if "expected_match_count" in case and len(matched) != int(case["expected_match_count"]):
            case_failures.append(f"expected match count {case['expected_match_count']} got {len(matched)}")
        if "expected_min_match_count" in case and len(matched) < int(case["expected_min_match_count"]):
            case_failures.append(f"expected at least {case['expected_min_match_count']} matches got {len(matched)}")
        if case["expected"] != FAMILY_SELECTION_CONTRACT_VIOLATION and matched != [case["expected"]]:
            case_failures.append(f"matched family ids not exactly expected family: {matched}")
        results.append(
            {
                "case_id": case["case_id"],
                "expected": case["expected"],
                "selected": selected,
                "matched_family_ids": matched,
                "raw_state_flags": result.get("raw_state_flags"),
                "classification_passed": result.get("classification_passed"),
                "failures": case_failures,
            }
        )
        failures.extend(f"{case['case_id']}: {failure}" for failure in case_failures)
    status = "PASS" if not failures else "FAIL"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    path = ARTIFACT_DIR / f"family_chooser_classification_regression_{timestamp}.json"
    payload = {
        "schema": "family_chooser_classification_regression.v1",
        "status": status,
        "case_count": len(CASES),
        "failures": failures,
        "cases": results,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{status}: {path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
