"""Proof that bending Ast-min cleanup checks width/depth relief before blocking."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET_BAND_SOURCE = ROOT / "design_brain" / "candidate_evaluation.py"

from design_brain.bending_overdesign_candidate_evaluation import (  # noqa: E402
    BendingOverdesignCandidateEvaluation,
    BendingOverdesignCandidateInput,
    BendingOverdesignCandidateUpdate,
    build_bending_overdesign_candidate_state_hash,
)
from design_brain.families.bending_overdesign_governs.contract import (  # noqa: E402
    lane_proof_policies,
    minimum_reinforcement_geometry_relief_rules,
    minimum_reinforcement_rules,
)
from design_brain.families.bending_overdesign_governs.runtime import (  # noqa: E402
    run_bending_overdesign_governs_runtime,
)


def _base_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 500.0,
        "bending_utilisation": 0.24,
        "As": 392.7,
        "As_min": 94.0,
        "bot1_count": 5,
        "db_bot_1": 10,
        "bot_row_count": 1,
    }


def _eval(
    candidate_input: BendingOverdesignCandidateInput,
    candidate_update: BendingOverdesignCandidateUpdate,
) -> BendingOverdesignCandidateEvaluation:
    updates = dict(candidate_update.updates)
    as_min = float(candidate_input.base_state.get("As_min") or 0.0)
    as_after = 392.7
    utilisation = 0.24
    if updates.get("b") == 275.0 and updates.get("bot1_count") == 4 and updates.get("db_bot_1") == 20:
        as_after = 1256.0
        utilisation = 0.82
    elif updates.get("b") == 275.0 and updates.get("bot_row_count") == 1 and updates.get("bot2_count") == 0:
        as_after = 392.7
        utilisation = 0.25
    elif updates.get("b") == 275.0:
        utilisation = 0.26
    elif updates.get("bot1_count") == 3 and updates.get("db_bot_1") == 20:
        as_after = 942.0
        utilisation = 1.04
    elif updates.get("bot1_count") or updates.get("db_bot_1"):
        as_after = 1256.0
        utilisation = 0.96
    valid = as_after >= as_min and utilisation <= 1.0
    return BendingOverdesignCandidateEvaluation(
        input_hash=candidate_input.input_hash,
        update_hash=candidate_update.update_hash,
        candidate_state_hash=build_bending_overdesign_candidate_state_hash(
            candidate_input.base_state,
            candidate_update.updates,
        ),
        bending_utilisation=utilisation,
        previous_bending_utilisation=0.24,
        target_band_status={"inside_target_band": 0.85 <= utilisation <= 1.0},
        utilisation_moves_toward_target=utilisation > 0.24 and utilisation <= 1.0,
        bending_remains_compliant=utilisation <= 1.0,
        constructability_status={"status": "PASS"},
        code_compliance_status={"status": "PASS" if valid else "FAIL"},
        minimum_reinforcement_status={
            "As": as_after,
            "As_min": as_min,
            "As_greater_than_or_equal_to_As_min": as_after >= as_min,
            "discard_before_ranking": as_after < as_min,
        },
        geometry_compliance_status={"status": "PASS"},
        beam_proportion_status={"status": "PASS"},
        reinforcement_quantity={"after": as_after},
        beam_volume={"after": float(updates.get("b") or 300.0) * float(updates.get("D") or 500.0)},
        cost_proxy={"after": 1.0},
        capacity_summary={"fixture": "bending_ast_min_geometry_relief"},
        failure_flags={"underdesign_created": utilisation > 1.0, "below_minimum_reinforcement": as_after < as_min},
        engineering_status={"candidate_valid": valid},
    ).with_evaluation_hash()


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_bending_ast_min_geometry_relief_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_ast_min_geometry_relief_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Bending Ast-min Geometry Relief Snapshot",
                "",
                f"Result: `{snapshot['result']}`",
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
    result = run_bending_overdesign_governs_runtime(base_state=_base_state(), evaluate_candidate=_eval)
    updates = [dict(row.get("updates") or {}) for row in result.candidate_repairs]
    inputs_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    target_band_source = TARGET_BAND_SOURCE.read_text(encoding="utf-8", errors="replace")
    relief_rules = minimum_reinforcement_geometry_relief_rules()
    width_policy = lane_proof_policies().get("width_reduction") or {}
    min_reo_text = json.dumps(minimum_reinforcement_rules(), sort_keys=True)
    checks = {
        "contract_has_ast_min_relief_rules": bool(relief_rules)
        and "Ast-min" in json.dumps(relief_rules, sort_keys=True)
        and "width reduction" in json.dumps(relief_rules, sort_keys=True).lower(),
        "minimum_reinforcement_blocker_names_ast_min": "Ast-min" in min_reo_text
        and "Width-reduction geometry relief" in min_reo_text
        and "Valid depth-reduction geometry relief" in min_reo_text,
        "width_policy_requires_restarted_reinforcement": width_policy.get("minimum_reinforcement_relief") is True
        and "width plus restarted bottom reinforcement candidate" in set(width_policy.get("restarted_candidate_requirements") or []),
        "depth_policy_requires_restarted_reinforcement": (lane_proof_policies().get("depth_reduction") or {}).get("minimum_reinforcement_relief") is True
        and "depth plus restarted bottom reinforcement candidate" in set(
            ((lane_proof_policies().get("depth_reduction") or {}).get("restarted_candidate_requirements") or [])
        ),
        "runtime_emits_width_plus_bottom_reinforcement": any(
            {"b", "bot1_count", "db_bot_1"} <= set(update) for update in updates
        ),
        "runtime_emits_width_plus_layer_reduction": any(
            update.get("b") is not None and update.get("bot_row_count") == 1 and update.get("bot2_count") == 0
            for update in updates
        ),
        "runtime_proof_counts_width_relief": result.minimum_reinforcement_proof.get(
            "minimum_reinforcement_geometry_relief_checked"
        )
        is True
        and result.restart_proof.get("width_reduction_restarted_reinforcement_candidate_count", 0) >= 2
        and result.restart_proof.get("depth_reduction_restarted_reinforcement_candidate_count", 0) >= 2,
        "visible_blocker_wording_mentions_ast_min": "minimum bending reinforcement (Ast-min" in inputs_source
        and "Width-reduction and valid depth-reduction geometry relief, with restarted bottom-reinforcement/layer routes, were checked" in inputs_source,
        "visible_blocker_stamps_ast_min_evidence": "minimum_bending_reinforcement_governs" in inputs_source
        and "width_reduction_as_min_relief_checked" in inputs_source
        and "depth_reduction_as_min_relief_checked" in inputs_source
        and "exact_stop_cleanup_proof_chain_complete" in inputs_source,
        "legacy_ast_min_ratio_heuristic_removed": "float(min_steel_util) >= float(bending_util) - 0.025" not in inputs_source,
        "ductility_cleanup_exact_stop_reason_is_explicit": "Ductility (k_u / ku) governs the remaining bending cleanup boundary." in inputs_source
        and "reo_reduction_attempted_first_for_ductility" in inputs_source,
        "live_search_checks_width_reduction_at_current_depth": "if float(min_depth) <= float(value) <= float(current_depth) + 1e-9" in target_band_source,
        "live_search_checks_width_plus_lighter_same_diameter_reo": "practical_bottom_trials.update" in target_band_source
        and "for bars1 in range(int(row1_bars) - 1, 0, -1)" in target_band_source,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "design_guide_bending_ast_min_geometry_relief_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "runtime": {
            "candidate_count": len(result.candidate_repairs),
            "width_reduction_relief_candidate_count": result.minimum_reinforcement_proof.get(
                "width_reduction_relief_candidate_count"
            ),
            "ladder_hash": result.ladder_hash,
        },
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("Design Guide bending Ast-min geometry relief FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("Design Guide bending Ast-min geometry relief PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
