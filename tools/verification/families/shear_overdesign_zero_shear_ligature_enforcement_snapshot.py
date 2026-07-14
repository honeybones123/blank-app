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

from design_brain.family_chooser import classify_family_from_raw_flags  # noqa: E402
from design_brain.family_classification_runtime import (  # noqa: E402
    classify_family_from_whole_beam_evidence,
)
from design_brain.families.shear_cleanup import ShearCleanupFamily  # noqa: E402
from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    lane_proof_policies,
    zero_shear_override,
)


def _write_snapshot(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_overdesign_zero_shear_ligature_enforcement_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_zero_shear_ligature_enforcement_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Zero-Shear Ligature Enforcement",
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


def _source_checks() -> dict[str, bool]:
    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="replace")
    zero_shear_helper = source.split("def _shear_no_demand_cleanup_guidance_item_if_needed", 1)[-1].split(
        "\ndef _shear_guidance_item", 1
    )[0]
    return {
        "page_detects_zero_shear_ligature_contract_signal": "_zero_shear_ligature_cleanup_contract_signal" in source,
        "page_routes_zero_shear_ligatures_before_terminal_pass": "shear_overdesign_zero_shear_ligature_removal" in source,
        "terminal_zero_shear_acceptance_requires_no_active_ligatures": (
            "not _zero_shear_ligature_cleanup_contract_signal(_terminal_current_state_for_shear)" in source
            and "not _zero_shear_ligature_cleanup_contract_signal(_render_current_state_for_shear)" in source
            and "not _zero_shear_ligature_cleanup_contract_signal(current_state)" in source
        ),
        "page_stamps_shear_overdesign_family_owner": "design_brain.families.shear_cleanup.ShearCleanupFamily" in source,
        "page_zero_shear_item_uses_resolved_candidate_action": (
            '"apply_resolved_candidate"' in zero_shear_helper
            and '"apply_shear_recommendation"' not in zero_shear_helper
        ),
        "page_zero_shear_item_publishes_enabled_button_contract": (
            '"button_contract": dict(button_contract)' in zero_shear_helper
            and '"actionable": True' in zero_shear_helper
            and '"preview_pass": True' in zero_shear_helper
            and '"blocking_reason": None' in zero_shear_helper
        ),
        "page_zero_shear_item_carries_resolved_candidate_updates": (
            '"resolved_candidate_updates": dict(updates)' in zero_shear_helper
            and '"resolved_candidate_family_tag": "SHEAR_OVERDESIGN_GOVERNS"' in zero_shear_helper
            and '"selected_strategy_lane": "LIGATURE_REMOVAL"' in zero_shear_helper
        ),
        "page_zero_shear_item_records_target_band_exception_proof": (
            '"target_band_exception_reason": "zero_shear_ligature_removal_contract"' in zero_shear_helper
        ),
    }


def main() -> int:
    override = zero_shear_override()
    policies = lane_proof_policies()
    removal_policy = dict(policies.get("ligature_removal") or {})
    raw_flags = {
        "geometry_detailing_fail": False,
        "serviceability_fail": False,
        "bending_fail": False,
        "shear_fail": False,
        "min_bending_reo_fail": False,
        "min_shear_reo_fail": False,
        "bending_overdesigned": False,
        "shear_overdesigned": False,
        "zero_shear_with_ligatures": True,
        "unnecessary_shear_reinforcement_exists": True,
        "shear_cleanup_possible": True,
        "bending_within_target_band": True,
        "shear_within_target_band": False,
        "locked_repair_blocked": False,
        "legal_repair_exists": True,
        "repair_required": False,
        "exact_stop_proven": True,
        "bending_acceptable": True,
        "shear_acceptable": True,
    }
    chooser_result = classify_family_from_raw_flags(
        raw_flags,
        evidence={"source": "zero_shear_ligature_enforcement_snapshot"},
    )
    runtime_result = classify_family_from_whole_beam_evidence(
        {
            "bending_utilisation": 0.94,
            "shear_utilisation": 0.0,
            "bending_state": "TARGET",
            "shear_state": "PASS",
            "serviceability_state": "PASS",
            "geometry_detailing_state": "PASS",
            "minimum_bending_reo_state": "PASS",
            "minimum_shear_reo_state": "PASS",
            "can_optimise_shear_without_hurting_bending": True,
            "exact_stop_available": True,
            "zero_shear_with_ligatures": True,
            "unnecessary_shear_reinforcement_exists": True,
            "shear_cleanup_possible": True,
        }
    )
    family = ShearCleanupFamily()
    specs = family.contracted_repair_ladder_specs(
        {
            "b": 400.0,
            "D": 650.0,
            "Vu": 0.0,
            "design_actions_present": True,
            "s_lig": 200.0,
            "lig_d": 10,
            "lig_legs": 2,
            "shear_utilisation": 0.0,
            "minimum_shear_reinforcement_required": False,
        }
    )
    candidate_specs = list(specs.get("specs") or [])
    selected = dict(specs.get("selected_recommendation") or {})
    selected_updates = dict(selected.get("updates") or {})
    checks = {
        "contract_zero_shear_override_requires_ligatures": (override.get("requires") or {}).get("ligatures_exist") is True,
        "contract_zero_shear_forbids_terminal_suppression": (
            override.get("family_cannot_terminate_solely_because_utilisation_is_zero") is True
        ),
        "contract_ligature_removal_canonical_update_removes_links": (
            dict(removal_policy.get("canonical_update") or {}) == {"lig_legs": 0, "lig_d": 0, "s_lig": 0}
        ),
        "raw_chooser_selects_shear_overdesign": chooser_result.get("selected_family_id") == "SHEAR_OVERDESIGN_GOVERNS",
        "raw_chooser_does_not_select_exact_stop": chooser_result.get("selected_family_id") != "EXACT_STOP_PROVEN",
        "contract_runtime_selects_shear_overdesign": runtime_result.get("selected_family_id") == "SHEAR_OVERDESIGN_GOVERNS",
        "contract_runtime_does_not_select_exact_stop": runtime_result.get("selected_family_id") != "EXACT_STOP_PROVEN",
        "family_runtime_emits_candidates": bool(candidate_specs),
        "family_runtime_selected_ligature_removal": selected.get("lane_id") == "LIGATURE_REMOVAL",
        "family_runtime_selected_update_removes_ligatures": (
            selected_updates.get("lig_legs") == 0
            and selected_updates.get("lig_d") == 0
        ),
        "family_runtime_selected_recommendation_is_executable": (
            selected.get("action_type") == "apply_resolved_candidate"
            and bool(selected_updates)
        ),
        "family_runtime_records_zero_shear_override_proof": bool(specs.get("zero_shear_override_proof")),
        **_source_checks(),
    }
    failures = sorted(key for key, value in checks.items() if not value)
    snapshot = {
        "schema": "shear_overdesign_zero_shear_ligature_enforcement.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "chooser_result": chooser_result,
        "classification_runtime_result": runtime_result,
        "runtime_selected_recommendation": selected,
        "runtime_ladder_hash": specs.get("ladder_hash"),
    }
    json_path, report_path = _write_snapshot(snapshot)
    if failures:
        print("SHEAR_OVERDESIGN_GOVERNS zero-shear ligature enforcement FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("SHEAR_OVERDESIGN_GOVERNS zero-shear ligature enforcement PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
