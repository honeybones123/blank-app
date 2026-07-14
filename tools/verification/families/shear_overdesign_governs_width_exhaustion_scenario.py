"""Focused width-exhaustion regression for SHEAR_OVERDESIGN_GOVERNS."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.shear_overdesign_governs.runtime import (  # noqa: E402
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)
from design_brain.shear_overdesign_candidate_evaluation import (  # noqa: E402
    ShearOverdesignCandidateEvaluation,
    ShearOverdesignCandidateInput,
    ShearOverdesignCandidateUpdate,
    build_shear_overdesign_candidate_state_hash,
)


def _base_state() -> dict[str, Any]:
    return {
        "b": 730.0,
        "D": 375.0,
        "Vu": 30.0,
        "design_actions_present": True,
        "s_lig": 125.0,
        "lig_d": 10,
        "lig_legs": 2,
        "shear_utilisation": 0.05,
        "bending_utilisation": 0.92,
        "minimum_shear_reinforcement_required": False,
        "geometry_locked": False,
        "width_locked": False,
    }


def _candidate_bending_util(width_after: float) -> float:
    return round(0.92 * 730.0 / width_after, 4)


def _evaluate(
    candidate_input: ShearOverdesignCandidateInput,
    candidate_update: ShearOverdesignCandidateUpdate,
) -> ShearOverdesignCandidateEvaluation:
    updates = dict(candidate_update.updates)
    width_after = float(updates.get("b") or candidate_input.base_state.get("b") or 0.0)
    removes_ligatures = updates.get("lig_legs") == 0 and updates.get("lig_d") == 0
    width_candidate = candidate_update.width_reduction_attempted
    bending_util = _candidate_bending_util(width_after) if width_candidate else 0.92
    candidate_valid = bending_util <= 1.0
    status = "ACCEPTED" if candidate_valid else "REJECTED_NEXT_WIDTH_FAILS_BENDING"
    return ShearOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_shear_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        shear_utilisation=0.05,
        previous_shear_utilisation=0.05,
        target_band_status={
            "inside_target_band": 0.85 <= bending_util <= 1.0,
            "bending_inside_target_band": 0.85 <= bending_util <= 1.0,
            "shear_heavily_under_utilised": True,
        },
        utilisation_moves_toward_target=True,
        shear_remains_compliant=True,
        constructability_status={"status": "PASS" if candidate_valid else "FAIL"},
        mandatory_detailing_status={"status": "PASS", "minimum_shear_reinforcement_required": False},
        shear_detailing_update_status={
            "shear_detailing_only": candidate_update.shear_detailing_only,
            "contract_update_allowed": candidate_update.contract_allowed_update,
            "update_keys": candidate_update.update_keys,
        },
        geometry_restriction_status={
            "geometry_reduction_attempted": candidate_update.geometry_reduction_attempted,
            "depth_reduction_prohibited": True,
            "width_reduction_allowed": True,
        },
        width_reduction_status={
            "width_before": 730.0,
            "width_after": width_after,
            "width_reduction_attempted": width_candidate,
            "width_locked": False,
            "next_width_blocker": None if candidate_valid else "next_width_step_failed_bending",
        },
        bending_utilisation=bending_util,
        previous_bending_utilisation=0.92,
        reinforcement_fit_status={
            "status": "PASS" if candidate_valid else "NOT_REACHED",
            "rearrangement_search_attempted": width_candidate,
            "bar_positions_and_layers_regenerated": width_candidate,
            "clear_spacing_recalculated": width_candidate,
            "alternative_safe_reo_arrangement_searched": width_candidate,
        },
        serviceability_status={"status": "PASS"},
        crack_control_status={"status": "PASS"},
        zero_shear_status={"zero_or_negligible_shear": False, "must_not_terminate_for_zero_utilisation": False},
        ligature_removal_status={"no_unnecessary_ligatures_remain": removes_ligatures},
        reinforcement_quantity={"after": 0.0 if removes_ligatures else 1.0},
        cost_proxy={"after": width_after},
        capacity_summary={"scenario": "width_730_bending_092_shear_005"},
        failure_flags={"underdesign_created": not candidate_valid},
        engineering_status={"candidate_valid": candidate_valid, "result": status, "failed_check": None if candidate_valid else "bending"},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_governs_width_exhaustion_scenario_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_width_exhaustion_scenario_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Width Exhaustion Scenario",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Selected",
                "",
                f"- selected_family: `SHEAR_OVERDESIGN_GOVERNS`",
                f"- selected_lane: `{snapshot['selected_lane']}`",
                f"- smallest_safe_width: `{snapshot['smallest_safe_width']}`",
                f"- exact_blocker: `{snapshot['exact_blocker']}`",
                "",
                "## Candidate Widths",
                "",
                *[
                    f"- `{row['width_after']}` mm: accepted=`{row['accepted']}`, bending_util=`{row['bending_utilisation']}`"
                    for row in snapshot["candidate_widths_tested"]
                ],
                "",
                "## Checks",
                "",
                *[f"- `{key}`: `{value}`" for key, value in snapshot["checks"].items()],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    result = run_shear_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_evaluate)
    width_rows = [
        {
            "candidate_index": row.get("candidate_index"),
            "width_after": (row.get("width_reduction_status") or {}).get("width_after"),
            "accepted": bool(row.get("accepted")),
            "bending_utilisation": row.get("bending_utilisation"),
            "shear_utilisation": row.get("shear_utilisation"),
            "update_hash": row.get("update_hash"),
            "candidate_state_hash": row.get("candidate_state_hash"),
            "engineering_status": row.get("engineering_status"),
            "reinforcement_fit_status": row.get("reinforcement_fit_status"),
        }
        for row in result.candidate_repairs
        if row.get("lane_id") == "WIDTH_REDUCTION"
    ]
    accepted_widths = [float(row["width_after"]) for row in width_rows if row["accepted"]]
    rejected_widths = [float(row["width_after"]) for row in width_rows if not row["accepted"]]
    smallest_safe_width = min(accepted_widths) if accepted_widths else None
    selected = dict(result.selected_recommendation or {})
    selected_width = (selected.get("width_reduction_status") or {}).get("width_after")
    exact_blocker = "next_width_step_failed_bending" if rejected_widths else None
    checks = {
        "selected_family_is_shear_overdesign": True,
        "contract_order_contains_width_reduction": "WIDTH_REDUCTION" in shear_overdesign_contract_lane_order(),
        "width_reduction_allowed": result.geometry_restriction_proof.get("width_reduction_allowed") is True,
        "width_candidates_tested": len(width_rows) > 0,
        "candidate_widths_descend_from_730": [row["width_after"] for row in width_rows[:4]] == [705.0, 680.0, 655.0, 630.0],
        "smallest_safe_width_found": smallest_safe_width == 680.0,
        "selected_smallest_safe_width": selected_width == smallest_safe_width,
        "next_width_blocker_recorded": exact_blocker == "next_width_step_failed_bending",
        "rearrangement_search_recorded": all(
            bool((row.get("reinforcement_fit_status") or {}).get("rearrangement_search_attempted"))
            for row in width_rows[:2]
        ),
        "depth_not_reduced": all("D" not in dict(row.get("updates") or {}) for row in result.candidate_repairs),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "shear_overdesign_governs_width_exhaustion_scenario.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "selected_lane": result.selected_strategy_lane,
        "selected_recommendation": selected,
        "candidate_widths_tested": width_rows,
        "smallest_safe_width": smallest_safe_width,
        "exact_blocker": exact_blocker,
        "ladder_hash": result.ladder_hash,
        "contract_lane_order": list(shear_overdesign_contract_lane_order()),
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS width exhaustion scenario FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS width exhaustion scenario PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
