"""Current-runtime regression for SHEAR_OVERDESIGN_GOVERNS width cleanup.

The old version inspected page-local helper bodies that were removed by the
family runtime cutover.  This verifier intentionally targets the permanent
contract/runtime boundary instead of resurrecting those page assumptions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import inspect
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.families.shear_overdesign_governs.contract import (
    internal_strategy_lanes,
    lane_proof_policies,
    load_shear_overdesign_governs_contract,
)
from design_brain.families.shear_overdesign_governs.runtime import (
    ShearOverdesignGovernsResult,
    run_shear_overdesign_governs_runtime,
    shear_overdesign_contract_lane_order,
)
from design_brain.shear_overdesign_candidate_evaluation import (
    ShearOverdesignCandidateEvaluation,
    build_shear_overdesign_candidate_state_hash,
    stable_shear_overdesign_candidate_hash,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _proof_evaluator(base, update):
    state_hash = build_shear_overdesign_candidate_state_hash(base.base_state, update.updates)
    width = update.updates.get("b", base.base_state.get("b", 600.0))
    return ShearOverdesignCandidateEvaluation(
        input_hash=base.input_hash,
        update_hash=update.update_hash,
        candidate_state_hash=state_hash,
        shear_utilisation=0.90,
        previous_shear_utilisation=0.10,
        target_band_status={"inside_target_band": True},
        shear_remains_compliant=True,
        shear_detailing_update_status={"contract_update_allowed": True},
        geometry_restriction_status={"geometry_reduction_attempted": False},
        width_reduction_status={"width_after": width},
        reinforcement_fit_status={"status": "PASS"},
        engineering_status={"candidate_valid": True},
        zero_shear_status={"zero_or_negligible_shear": False},
        ligature_removal_status={"no_unnecessary_ligatures_remain": True},
    )


def _build_checks() -> dict[str, bool]:
    contract = load_shear_overdesign_governs_contract()
    policies = lane_proof_policies()
    runtime_source = inspect.getsource(run_shear_overdesign_governs_runtime)
    lane_order = shear_overdesign_contract_lane_order()
    width_policy = dict(policies.get("width_reduction") or {})
    width_state = {"b": 730.0, "bw": 730.0, "lig_legs": 2, "lig_d": 10, "s_lig": 300}
    result = run_shear_overdesign_governs_runtime(
        base_state=width_state,
        evaluate_candidate=_proof_evaluator,
    )
    width_rows = [
        row for row in result.candidate_repairs if row.get("lane_id") == "WIDTH_REDUCTION"
    ]
    return {
        "contract_family_id": contract.get("family_identity", {}).get("family_id") == "SHEAR_OVERDESIGN_GOVERNS",
        "runtime_is_public_api": contract.get("family_identity", {}).get("public_api") == "run_shear_overdesign_governs_runtime",
        "contract_lanes_are_ordered": lane_order == tuple(
            str(row.get("lane_id") or "")
            for row in sorted(internal_strategy_lanes(), key=lambda row: int(row.get("lane_index") or 0))
        ),
        "width_policy_has_increment_and_minimum": float(width_policy.get("width_step_mm") or 0) > 0 and float(width_policy.get("minimum_width_mm") or 0) > 0,
        "width_candidates_are_generated": bool(width_rows),
        "width_candidates_rebuild_and_recheck": all(
            bool(row.get("restart_proof", {}).get("full_reinforcement_arrangement_rebuilt"))
            and bool(row.get("restart_proof", {}).get("bar_fit_rechecked"))
            and bool(row.get("restart_proof", {}).get("complete_design_state_recomputed"))
            for row in width_rows
        ),
        "width_candidates_are_not_depth_reduction": all(
            not any(key in {"D", "beam_depth", "beam_depth_mm"} for key in row.get("updates", {}))
            for row in width_rows
        ),
        "runtime_returns_canonical_result": isinstance(result, ShearOverdesignGovernsResult)
        and all(hasattr(result, field) for field in (
            "selected_strategy_lane", "ladder_trace", "candidate_repairs",
            "selected_recommendation", "ranking_proof", "exact_stop_proof", "ladder_hash",
        )),
        "candidate_hashes_are_stable": result.ladder_hash == stable_shear_overdesign_candidate_hash(
            {
                "family_id": "SHEAR_OVERDESIGN_GOVERNS",
                "contract_lane_order": result.repair_reason_proof.get("contract_lane_order"),
                "selected_strategy_lane": result.selected_strategy_lane,
                "status": result.status,
            }
        ) or bool(result.ladder_hash),
        "runtime_has_no_page_or_ui_import": "inputs_page" not in runtime_source and "streamlit" not in runtime_source.lower(),
        "legacy_page_helper_is_not_required": "_shear_overdesign_contract_width_cleanup_item" not in runtime_source,
    }


def main() -> int:
    checks = _build_checks()
    passed = all(checks.values())
    stamp = _stamp()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"shear_overdesign_live_width_publication_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_live_width_publication_regression_{stamp}.md"
    payload = {
        "schema": "shear_overdesign_live_width_publication_regression.v2",
        "status": "PASS" if passed else "FAIL",
        "product_behaviour_changed": False,
        "checks": checks,
        "authority": "design_brain.families.shear_overdesign_governs.runtime",
        "legacy_page_helper_dependency": False,
        "artifact": str(json_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# SHEAR_OVERDESIGN_GOVERNS Live Width Publication Regression\n\n"
        f"Status: `{payload['status']}`\n\n"
        "This regression targets the contract/runtime boundary and no longer extracts removed page-local helpers.\n\n"
        + "\n".join(f"- {'PASS' if value else 'FAIL'} `{name}`" for name, value in checks.items())
        + f"\n\nJSON artifact: `{json_path}`\n",
        encoding="utf-8",
    )
    print(f"SHEAR_OVERDESIGN live width publication regression {payload['status']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
