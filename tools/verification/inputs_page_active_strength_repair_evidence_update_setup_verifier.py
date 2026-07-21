from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_active_strength_repair_evidence_update_setup_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_active_strength_repair_evidence_update_setup_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_resolve_recommendation_updates": inputs_page._resolve_recommendation_updates,
        "_active_repair_with_residual_shear_target_cleanup": inputs_page._active_repair_with_residual_shear_target_cleanup,
        "_design_mode_config": inputs_page._design_mode_config,
        "_design_optimisation_goal": inputs_page._design_optimisation_goal,
    }
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for name, value in originals.items():
            setattr(inputs_page, name, value)

    try:
        merge_calls: list[dict[str, Any]] = []
        inputs_page._resolve_recommendation_updates = lambda item, *, state: {"from_recommendation": True}
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"

        def _merge(state, updates, *, active_family, mode_config):
            merge_calls.append(
                {
                    "state": dict(state),
                    "updates": dict(updates),
                    "active_family": active_family,
                    "mode_config": dict(mode_config),
                }
            )
            return {
                "updates": {"best": True, "merged_shear": True},
                "evidence": {"merged": True, "selected_candidate_id": "merged-evidence-id"},
            }

        inputs_page._active_repair_with_residual_shear_target_cleanup = _merge
        item, contract, evidence, updates, expected_util, merged = (
            inputs_page.render_design_guide_active_strength_repair_evidence_update_setup(
                active_repair_item={
                    "candidate_search_evidence": {
                        "target_band_candidate_count": 2,
                        "best_target_band_candidate_updates": {"best": True},
                        "best_target_band_candidate_util": "0.91",
                        "best_target_band_candidate_id": "best-id",
                    },
                    "button_contract": {"updates": {"contract": True}},
                },
                active_repair_contract={"updates": {"contract": True}, "expected_util": 0.5},
                active_repair_family="combined",
                guidance_disp_state={"depth": 500},
                guidance_debug={"candidate_search_evidence": {"debug": True}},
            )
        )
    finally:
        _restore()
    cases.append(
        {
            "name": "best_target_band_precedence_and_merge",
            "item": item,
            "contract": contract,
            "evidence": evidence,
            "updates": updates,
            "expected_util": expected_util,
            "merged": merged,
            "merge_calls": merge_calls,
        }
    )
    if updates != {"best": True, "merged_shear": True}:
        failures.append(f"best_updates_mismatch:{updates}")
    if expected_util != 0.91:
        failures.append(f"best_expected_util_mismatch:{expected_util}")
    if evidence.get("merged") is not True:
        failures.append(f"merge_evidence_not_folded:{evidence}")
    if contract.get("updates") != updates:
        failures.append(f"contract_updates_mismatch:{contract}")
    if contract.get("candidate_id") != "best-id" or contract.get("source_candidate_id") != "best-id":
        failures.append(f"contract_candidate_id_mismatch:{contract}")
    if item.get("active_repair_includes_residual_shear_cleanup") is not True:
        failures.append(f"merged_flag_missing:{item}")
    if item.get("residual_shear_cleanup_evidence") != {"merged": True, "selected_candidate_id": "merged-evidence-id"}:
        failures.append(f"merged_evidence_item_mismatch:{item}")
    if not merge_calls or merge_calls[0].get("mode_config") != {"goal": "efficiency"}:
        failures.append(f"merge_call_mismatch:{merge_calls}")

    try:
        merge_calls = []
        rec_calls: list[dict[str, Any]] = []

        def _recommendation(item_arg, *, state):
            rec_calls.append({"item": dict(item_arg), "state": dict(state)})
            return {"recommended": True}

        inputs_page._resolve_recommendation_updates = _recommendation
        inputs_page._design_mode_config = lambda goal: {"goal": goal}
        inputs_page._design_optimisation_goal = lambda state: "efficiency"
        inputs_page._active_repair_with_residual_shear_target_cleanup = (
            lambda state, updates, *, active_family, mode_config: merge_calls.append(
                {
                    "state": dict(state),
                    "updates": dict(updates),
                    "active_family": active_family,
                    "mode_config": dict(mode_config),
                }
            )
            or {}
        )
        item, contract, evidence, updates, expected_util, merged = (
            inputs_page.render_design_guide_active_strength_repair_evidence_update_setup(
                active_repair_item={"candidate_id": "item-id"},
                active_repair_contract={"expected_util": "0.77"},
                active_repair_family="bending",
                guidance_disp_state={"depth": 450},
                guidance_debug={"candidate_search_evidence": {"selected_candidate_id": "debug-id"}},
            )
        )
    finally:
        _restore()
    cases.append(
        {
            "name": "recommendation_fallback_without_merge_updates",
            "item": item,
            "contract": contract,
            "evidence": evidence,
            "updates": updates,
            "expected_util": expected_util,
            "merged": merged,
            "merge_calls": merge_calls,
            "rec_calls": rec_calls,
        }
    )
    if updates != {"recommended": True}:
        failures.append(f"recommendation_updates_mismatch:{updates}")
    if expected_util != 0.77:
        failures.append(f"recommendation_expected_util_mismatch:{expected_util}")
    if contract.get("candidate_id") != "debug-id":
        failures.append(f"recommendation_candidate_id_mismatch:{contract}")
    if item.get("candidate_id") != "debug-id" or item.get("source_candidate_id") != "debug-id":
        failures.append(f"recommendation_item_candidate_id_mismatch:{item}")
    if merged != {}:
        failures.append(f"recommendation_merged_should_be_empty:{merged}")
    if not rec_calls:
        failures.append("recommendation_fallback_not_called")

    try:
        merge_calls = []
        inputs_page._resolve_recommendation_updates = lambda item, *, state: {"recommended": True}
        inputs_page._active_repair_with_residual_shear_target_cleanup = lambda *args, **kwargs: merge_calls.append(kwargs) or {}
        item, contract, evidence, updates, expected_util, merged = (
            inputs_page.render_design_guide_active_strength_repair_evidence_update_setup(
                active_repair_item={"updates": {"item": True}},
                active_repair_contract={},
                active_repair_family="serviceability",
                guidance_disp_state={"depth": 500},
                guidance_debug={},
            )
        )
    finally:
        _restore()
    cases.append(
        {
            "name": "non_strength_family_skips_residual_merge",
            "item": item,
            "contract": contract,
            "evidence": evidence,
            "updates": updates,
            "expected_util": expected_util,
            "merged": merged,
            "merge_calls": merge_calls,
        }
    )
    if updates != {"item": True}:
        failures.append(f"non_strength_updates_mismatch:{updates}")
    if merge_calls:
        failures.append(f"non_strength_merge_called:{merge_calls}")
    if contract.get("updates") != {"item": True}:
        failures.append(f"non_strength_contract_updates_mismatch:{contract}")

    payload = {
        "verifier": "inputs_page_active_strength_repair_evidence_update_setup_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Active Strength Repair Evidence Update Setup Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
