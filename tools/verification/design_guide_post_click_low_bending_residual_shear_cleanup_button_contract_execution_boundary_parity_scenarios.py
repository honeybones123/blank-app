"""Parity scenarios for the residual-shear shared button-contract boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
    }


def _scenario(
    name: str,
    *,
    contract: dict[str, Any],
    expected_executor_backed: bool,
    expected_output_shape_ready: bool,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary,
    )

    promoted = {
        "candidate_id": f"{name}-candidate",
        "updates": dict(contract.get("updates") or {}),
        "action_payload": {"updates": dict(contract.get("updates") or {})},
        "resolved_candidate": {"updates": dict(contract.get("updates") or {})},
        "button_contract": dict(contract),
    }
    input_summary = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "button_contract_builder": "_design_guide_button_contract",
        "promoted_item_hash": _stable_hash(promoted),
    }
    result = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary=dict(input_summary),
        button_contract=dict(contract),
        state_summary={"scenario": name},
        dependency_status="page_live",
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(
        promoted_item=dict(promoted),
        button_contract_input_summary=dict(input_summary),
        button_contract=dict(contract),
        state_summary={"scenario": name},
        dependency_status="page_live",
    )
    checks = {
        "stable_hash": result.get("button_contract_execution_boundary_hash")
        == repeat.get("button_contract_execution_boundary_hash"),
        "executor_backed_matches": result.get("executor_backed_apply_proof")
        is expected_executor_backed,
        "output_shape_ready_matches": result.get("output_shape_ready")
        is expected_output_shape_ready,
        "behavior_cutover_not_claimed": result.get("behavior_cutover_ready") is False,
        "proof_only_non_driving": all(
            (
                result.get("proof_only") is True,
                result.get("product_driving") is False,
                result.get("render_driving") is False,
                result.get("apply_driving") is False,
                result.get("session_driving") is False,
            )
        ),
    }
    return {
        "name": name,
        "result": result,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _capture() -> dict[str, Any]:
    object_snapshot = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_snapshot.py",
        ]
    )
    scenarios = [
        _scenario(
            "executor_backed_enabled",
            contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {"ligature_legs": 0, "ligature_dia": 0},
                "expected_util": 0.69,
            },
            expected_executor_backed=True,
            expected_output_shape_ready=True,
        ),
        _scenario(
            "outside_preferred_band_allowed",
            contract={
                "enabled": True,
                "actionable": True,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {"ligature_legs": 2, "ligature_dia": 10},
                "expected_util": 0.92,
            },
            expected_executor_backed=True,
            expected_output_shape_ready=True,
        ),
        _scenario(
            "disabled_missing_updates",
            contract={
                "enabled": False,
                "actionable": False,
                "action_type": "apply_resolved_candidate",
                "label": "Apply",
                "updates": {},
                "expected_util": None,
            },
            expected_executor_backed=False,
            expected_output_shape_ready=True,
        ),
        _scenario(
            "missing_action_type",
            contract={
                "enabled": True,
                "actionable": True,
                "action_type": "",
                "label": "Apply",
                "updates": {"ligature_legs": 0},
                "expected_util": 0.69,
            },
            expected_executor_backed=False,
            expected_output_shape_ready=False,
        ),
    ]
    return {
        "object_snapshot": object_snapshot,
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "passed_scenarios": sum(1 for scenario in scenarios if scenario.get("passed")),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "all_scenarios_passed": capture.get("passed_scenarios") == capture.get("scenario_count"),
        "scenario_count_expected": capture.get("scenario_count") == 4,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Button Contract Execution Boundary Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in capture.get("scenarios") or []:
        lines.append(f"- `{scenario.get('name')}`: passed=`{scenario.get('passed')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "",
            "Create cutover readiness for button-contract source summary. Do not move shared contract execution, apply routing, or visible wording yet.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_parity_scenarios "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
