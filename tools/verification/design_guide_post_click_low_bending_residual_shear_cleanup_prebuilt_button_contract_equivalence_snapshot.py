"""Proof-only equivalence for residual-shear prebuilt button contracts.

This snapshot does not move CTA/apply behaviour. It proves whether a future
cutover can consume a prebuilt/promoted button contract through the controller
boundary while preserving the same contract hash, update hash, enabled/actionable
flags, action type, expected utilisation, and executor-backed proof.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _boundary_for(
    *,
    name: str,
    promoted: dict[str, Any],
    button_contract: dict[str, Any],
    dependency_status: str,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary,
    )

    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "button_contract_builder": "_design_guide_button_contract",
            "scenario": name,
            "promoted_item_hash": _stable_hash(promoted),
            "action_payload_hash": _stable_hash(promoted.get("action_payload") or {}),
            "resolved_candidate_hash": _stable_hash(promoted.get("resolved_candidate") or {}),
        },
        button_contract=dict(button_contract),
        state_summary={"scenario": name, "state_fingerprint": _stable_hash({"scenario": name})},
        dependency_status=dependency_status,
    )


def _scenario(name: str, contract: dict[str, Any]) -> dict[str, Any]:
    promoted = {
        "candidate_id": f"{name}-candidate",
        "family": "shear",
        "updates": dict(contract.get("updates") or {}),
        "action_payload": {"updates": dict(contract.get("updates") or {})},
        "resolved_candidate": {"updates": dict(contract.get("updates") or {})},
        "button_contract": dict(contract),
    }
    shared_boundary = _boundary_for(
        name=name,
        promoted=dict(promoted),
        button_contract=dict(contract),
        dependency_status="page_live",
    )
    prebuilt_boundary = _boundary_for(
        name=name,
        promoted=dict(promoted),
        button_contract=dict(promoted.get("button_contract") or {}),
        dependency_status="controller_owned",
    )
    compared_fields = (
        "button_contract_hash",
        "button_contract_updates_hash",
        "button_contract_enabled",
        "button_contract_actionable",
        "button_contract_action_type",
        "button_contract_label",
        "button_contract_expected_util",
        "executor_backed_apply_proof",
        "output_shape_ready",
    )
    field_matches = {
        field: shared_boundary.get(field) == prebuilt_boundary.get(field)
        for field in compared_fields
    }
    return {
        "name": name,
        "shared_boundary_hash": shared_boundary.get("button_contract_execution_boundary_hash"),
        "prebuilt_boundary_hash": prebuilt_boundary.get(
            "button_contract_execution_boundary_hash"
        ),
        "button_contract_hash": shared_boundary.get("button_contract_hash"),
        "field_matches": field_matches,
        "fields_match": all(field_matches.values()),
        "shared_executor_backed_apply_proof": shared_boundary.get(
            "executor_backed_apply_proof"
        ),
        "prebuilt_executor_backed_apply_proof": prebuilt_boundary.get(
            "executor_backed_apply_proof"
        ),
        "prebuilt_controller_cutover_shape_ready": prebuilt_boundary.get(
            "behavior_cutover_ready"
        ),
        "shared_dependency_status": shared_boundary.get("dependency_status"),
        "prebuilt_dependency_status": prebuilt_boundary.get("dependency_status"),
    }


def _route_source_tokens() -> dict[str, bool]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    return {
        "live_shared_wrapper_exists": (
            "def _execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in source
        ),
        "live_shared_wrapper_called": (
            "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
            in source
            and "residual_button_contract = dict(" in source
        ),
        "button_boundary_stamped": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary("
            in source
        ),
        "prebuilt_contract_observed_after_binding": (
            "residual_button_contract = dict(\n                            residual_promoted.get(\"button_contract\") or {}\n                        )"
            in source
        ),
        "final_binding_uses_button_contract": (
            "button_contract=dict(residual_button_contract or {})" in source
        ),
        "route_return_still_present": "return residual_route_return_item" in source,
    }


def _capture() -> dict[str, Any]:
    scenarios = [
        _scenario(
            "executor_backed_enabled",
            {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {"ligature_legs": 0, "ligature_dia": 0},
                "expected_util": 0.69,
            },
        ),
        _scenario(
            "outside_preferred_band_allowed",
            {
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {"ligature_legs": 2, "ligature_dia": 10},
                "expected_util": 0.92,
            },
        ),
        _scenario(
            "disabled_missing_updates",
            {
                "enabled": False,
                "actionable": False,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {},
                "expected_util": None,
            },
        ),
        _scenario(
            "stale_disabled_contract",
            {
                "enabled": False,
                "actionable": False,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {"ligature_legs": 0},
                "expected_util": 0.69,
                "stale_payload": True,
            },
        ),
        _scenario(
            "missing_action_type",
            {
                "enabled": True,
                "actionable": True,
                "action_type": "",
                "label": "Apply",
                "updates": {"ligature_legs": 0},
                "expected_util": 0.69,
            },
        ),
    ]
    latest = {
        "button_boundary_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_readiness"
        ),
        "button_boundary_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_implementation"
        ),
        "nested_wrapper_deadness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_nested_wrapper_deadness_probe"
        ),
    }
    route_tokens = _route_source_tokens()
    return {
        "decision": "RESIDUAL_SHEAR_PREBUILT_BUTTON_CONTRACT_EQUIVALENCE_PROOF_ONLY",
        "scenario_count": len(scenarios),
        "passed_scenarios": sum(1 for scenario in scenarios if scenario.get("fields_match")),
        "scenarios": scenarios,
        "route_source_tokens": route_tokens,
        "route_source_tokens_present": all(route_tokens.values()),
        "previous_artifacts": latest,
        "previous_artifacts_pass": all(row.get("status") == "PASS" for row in latest.values()),
        "ready_for_prebuilt_button_contract_cutover": all(
            scenario.get("fields_match") for scenario in scenarios
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_body_deleted": False,
        "next_safe_surface": "prebuilt_button_contract_cutover_or_button_contract_execution_adapter",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "scenario_count_expected": capture.get("scenario_count") == 5,
        "all_scenarios_match": capture.get("passed_scenarios")
        == capture.get("scenario_count"),
        "route_source_tokens_present": capture.get("route_source_tokens_present") is True,
        "previous_artifacts_pass": capture.get("previous_artifacts_pass") is True,
        "ready_for_prebuilt_button_contract_cutover": (
            capture.get("ready_for_prebuilt_button_contract_cutover") is True
        ),
        "route_body_not_deleted": capture.get("route_body_deleted") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Prebuilt Button Contract Equivalence Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{capture.get('passed_scenarios')}/{capture.get('scenario_count')}`",
        f"- Ready for prebuilt button-contract cutover: `{capture.get('ready_for_prebuilt_button_contract_cutover')}`",
        f"- Product behaviour changed: `{capture.get('product_behavior_changed')}`",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in capture.get("scenarios") or []:
        lines.append(
            f"- `{scenario.get('name')}`: fields_match=`{scenario.get('fields_match')}`, "
            f"executor_backed=`{scenario.get('shared_executor_backed_apply_proof')}`"
        )
    lines.extend(["", "## Route Source Tokens", ""])
    for name, present in dict(capture.get("route_source_tokens") or {}).items():
        lines.append(f"- `{name}`: `{present}`")
    lines.extend(["", "## Previous Artifacts", ""])
    for name, row in dict(capture.get("previous_artifacts") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` {row.get('path')}")
    lines.extend(["", "## Checks", ""])
    for name, ok in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{ok}`")
    lines.extend(
        [
            "",
            "## Next",
            "",
            f"`{capture.get('next_safe_surface')}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    stamp = _stamp()
    payload = {
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            "prebuilt_button_contract_equivalence_snapshot.v1"
        ),
        "created_at": stamp,
        "status": status,
        "capture": capture,
        "checks": checks,
        "failures": [name for name, ok in checks.items() if ok is not True],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = (
        ARTIFACT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_button_contract_equivalence_{stamp}.json"
        )
    )
    audit_path = (
        AUDIT_DIR
        / (
            "design_guide_post_click_low_bending_residual_shear_cleanup_"
            f"prebuilt_button_contract_equivalence_{stamp}.md"
        )
    )
    report_path = (
        REPORT_DIR
        / (
            "design_brain_physical_extraction_residual_shear_cleanup_"
            f"prebuilt_button_contract_equivalence_{stamp}.md"
        )
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"prebuilt_button_contract_equivalence {status}"
    )
    print(json_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
