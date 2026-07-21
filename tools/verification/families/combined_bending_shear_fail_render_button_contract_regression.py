"""Regression for combined active-fail render button contract actionability.

The family/publication layer may publish an executor-backed strengthening CTA
whose resulting utilisation is below the cleanup target band. That is valid for
active strength repair when required checks pass. The render-facing button
contract must not reclassify that CTA as advisory just because cleanup
target-band policy would reject it.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.publication import (  # noqa: E402
    DesignGuideButtonContractActionabilityProbeOutputs,
    resolve_design_guide_button_contract_actionability_scalars,
)
import inputs_page_app_contract_bridge as inputs_page_module  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _active_repair_item() -> dict:
    updates = {"b": 450.0, "D": 750.0, "top1_count": 2, "db_top_1": 20}
    evidence = {
        "search_scope": "design_guide_active_strength_repair",
        "safe_executor_backed_candidates_count": 2,
        "outside_target_band_allowed": True,
        "outside_target_band_allowed_category": "active_strength_repair_passes_required_checks",
        "selected_candidate_id": "candidate_000",
        "selected_candidate_updates": dict(updates),
        "selected_candidate_util": 0.36,
    }
    return {
        "title_main": "Bending and shear capacity are low",
        "action_type": "apply_resolved_candidate",
        "family": "combined",
        "selected_action_family": "combined",
        "guidance_intent": "required_fix",
        "updates": dict(updates),
        "selected_action_updates": dict(updates),
        "candidate_search_evidence": dict(evidence),
        "button_contract": {
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": dict(updates),
            "executor_backed": True,
            "preview_pass": True,
            "source_candidate_id": "candidate_000",
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": dict(updates),
            "resolved_candidate_updates": dict(updates),
            "candidate_search_evidence": dict(evidence),
            "candidate_id": "candidate_000",
        },
    }


def _cleanup_item_without_active_repair_proof() -> dict:
    updates = {"bot_row_1_bars": 5}
    return {
        "title_main": "Bending cleanup",
        "action_type": "apply_resolved_candidate",
        "family": "bending",
        "guidance_intent": "efficiency_tightening",
        "updates": dict(updates),
        "candidate_search_evidence": {
            "search_scope": "design_guide_bending_only_cleanup",
            "safe_executor_backed_candidates_count": 1,
            "selected_candidate_updates": dict(updates),
        },
        "button_contract": {
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "updates": dict(updates),
            "executor_backed": True,
            "preview_pass": False,
        },
    }


def _resolve(
    item: dict,
    *,
    preview_reason: str = "candidate_preview_not_in_target_band_after_active_failure",
):
    return resolve_design_guide_button_contract_actionability_scalars(
        item_index=0,
        item=dict(item),
        updates=dict(item.get("updates") or {}),
        action_type="apply_resolved_candidate",
        update_decision_reason="regression",
        updates_source="regression",
        probe_inputs=None,
        raw_probe_outputs=DesignGuideButtonContractActionabilityProbeOutputs(
            item_index=0,
            executor_contract_evaluated=True,
            executor_allowed=True,
            executor_reason=None,
            preview_evaluated=True,
            preview_pass=False,
            preview_util=0.36,
            preview_reason=preview_reason,
            final_family=str(item.get("family") or ""),
            final_expected_util=0.36,
            final_blocking_reason=None,
            final_executor_allowed=True,
            final_preview_pass=False,
        ),
        blocking_reason_before=None,
        executor_allowed_before=True,
        preview_pass_before=False,
        expected_util_before=None,
        family_before=str(item.get("family") or ""),
        actionable_before=False,
        enabled_before=False,
    )


def _write(snapshot: dict) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"combined_bending_shear_fail_render_button_contract_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"combined_bending_shear_fail_render_button_contract_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Combined Bending/Shear Render Button Contract Regression",
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
    active = _resolve(_active_repair_item())
    active_local_preview_false = _resolve(
        _active_repair_item(),
        preview_reason="candidate_preview_still_fails_active_check",
    )
    cleanup = _resolve(_cleanup_item_without_active_repair_proof())
    projected_items = inputs_page_module._design_guide_apply_button_contracts_to_items(
        [_active_repair_item()],
        state={},
    )
    projection_contract = dict((projected_items[0] if projected_items else {}).get("button_contract") or {})
    projection_applied = bool(projected_items and projection_contract)
    active_payload = active.to_dict()
    active_local_preview_false_payload = active_local_preview_false.to_dict()
    cleanup_payload = cleanup.to_dict()
    checks = {
        "active_repair_enabled": active.enabled is True,
        "active_repair_actionable": active.actionable is True,
        "active_repair_preview_pass_promoted": active.preview_pass is True,
        "active_repair_blocking_reason_cleared": active.blocking_reason in (None, ""),
        "active_repair_local_preview_false_still_enabled": active_local_preview_false.enabled is True,
        "active_repair_local_preview_false_actionable": active_local_preview_false.actionable is True,
        "active_repair_local_preview_false_reason_cleared": active_local_preview_false.blocking_reason in (None, ""),
        "active_repair_render_projection_applied": projection_applied is True,
        "active_repair_render_projection_uses_current_bridge": bool(
            callable(getattr(inputs_page_module, "_design_guide_apply_button_contracts_to_items", None))
        ),
        "active_repair_empty_state_projection_blocks_preview": inputs_page_module._design_guide_button_contract_enabled(
            projection_contract
        )
        is not True
        and projection_contract.get("blocking_reason") == "candidate_preview_introduces_fail_status",
        "active_repair_render_projection_updates_present": bool(
            dict(projection_contract.get("updates") or {})
        ),
        "cleanup_without_active_repair_proof_still_blocked": cleanup.enabled is not True,
        "cleanup_without_active_repair_proof_preview_not_promoted": cleanup.preview_pass is not True,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    snapshot = {
        "schema": "combined_bending_shear_fail_render_button_contract_regression.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "active_repair_scalar_result": active_payload,
        "active_repair_local_preview_false_scalar_result": active_local_preview_false_payload,
        "active_repair_render_projection_contract": dict(projection_contract),
        "cleanup_control_scalar_result": cleanup_payload,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("combined bending/shear render button contract regression FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("combined bending/shear render button contract regression PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
