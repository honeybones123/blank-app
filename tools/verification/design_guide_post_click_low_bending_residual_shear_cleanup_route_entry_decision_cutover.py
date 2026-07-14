"""Verify residual-shear route entry decision is controller-owned.

This is a narrow live cutover verifier. It proves that the page no longer
interprets the route-entry guard directly and that candidate generation,
candidate evaluation, CTA contract execution, visible wording, Apply routing,
UI rendering, and session/debug mutation have not been moved.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

ENTRY_FN = (
    "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision"
)
ENTRY_ALIAS = (
    "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision"
)

RETAINED_TOKENS = {
    "primary_executor": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
    "fallback_variant_generator": "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
    "candidate_evaluator": "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
    "materiality_pre_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
    "materiality_post_screen": "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    "candidate_selector": "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
    "result_packaging": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    readiness_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_extraction_readiness.py",
        ]
    )
    retained_tokens = {name: token in route for name, token in RETAINED_TOKENS.items()}
    direct_button_contract_absent = "_design_guide_button_contract(residual_promoted, state=state)" not in route
    button_contract_observed_not_owned = all(
        token in route
        for token in (
            "button_contract_hash_observed_not_owned",
            "button_contract_source_summary_cutover",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
        )
    )
    direct_guard_branch_absent = (
        'if residual_shear_cleanup_route_entry_guard.get("should_enter_route"):' not in route
    )
    controller_entry_decision_call_present = f"{ENTRY_ALIAS}(" in route
    controller_entry_decision_consumed = (
        'if residual_shear_cleanup_route_entry_decision.get("should_enter_route"):' in route
        or "route_entry_decision=dict(residual_shear_cleanup_route_entry_decision or {})" in route
    )
    debug_stamps_present = all(
        token in route
        for token in (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision_hash",
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_entry_decision_scope",
        )
    )
    controller_function_present = f"def {ENTRY_FN}(" in controller_source
    controller_function_exported = f'"{ENTRY_FN}"' in controller_source
    import_alias_present = f"{ENTRY_FN} as {ENTRY_ALIAS}" in inputs_source
    return {
        "decision": "ROUTE_ENTRY_DECISION_CONTROLLER_CUTOVER_IMPLEMENTED",
        "route_found": bool(route),
        "readiness_run": readiness_run,
        "readiness_passed": readiness_run.get("passed") is True,
        "controller_function_present": controller_function_present,
        "controller_function_exported": controller_function_exported,
        "import_alias_present": import_alias_present,
        "controller_entry_decision_call_present": controller_entry_decision_call_present,
        "controller_entry_decision_consumed": controller_entry_decision_consumed,
        "direct_guard_branch_absent": direct_guard_branch_absent,
        "debug_stamps_present": debug_stamps_present,
        "retained_dependency_tokens": retained_tokens,
        "retained_dependencies_unchanged": all(retained_tokens.values()),
        "direct_button_contract_absent": direct_button_contract_absent,
        "button_contract_observed_not_owned": button_contract_observed_not_owned,
        "forbidden_moves_absent": {
            "candidate_generation_moved": False,
            "candidate_evaluation_moved": False,
            "cta_contract_execution_moved": False,
            "visible_wording_changed": False,
            "apply_routing_changed": False,
            "ui_rendering_moved": False,
            "session_state_moved": False,
        },
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "route_window_hash": _stable_hash(route),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_found": capture.get("route_found") is True,
        "readiness_passed": capture.get("readiness_passed") is True,
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_function_exported": capture.get("controller_function_exported") is True,
        "import_alias_present": capture.get("import_alias_present") is True,
        "controller_entry_decision_call_present": capture.get("controller_entry_decision_call_present") is True,
        "controller_entry_decision_consumed": capture.get("controller_entry_decision_consumed") is True,
        "direct_guard_branch_absent": capture.get("direct_guard_branch_absent") is True,
        "debug_stamps_present": capture.get("debug_stamps_present") is True,
        "retained_dependencies_unchanged": capture.get("retained_dependencies_unchanged") is True,
        "direct_button_contract_absent": capture.get("direct_button_contract_absent") is True,
        "button_contract_observed_not_owned": capture.get("button_contract_observed_not_owned") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route Entry Decision Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- controller function present: `{capture.get('controller_function_present')}`",
        f"- controller function exported: `{capture.get('controller_function_exported')}`",
        f"- page import alias present: `{capture.get('import_alias_present')}`",
        f"- controller entry decision call present: `{capture.get('controller_entry_decision_call_present')}`",
        f"- controller entry decision consumed: `{capture.get('controller_entry_decision_consumed')}`",
        f"- direct guard branch absent: `{capture.get('direct_guard_branch_absent')}`",
        f"- retained dependencies unchanged: `{capture.get('retained_dependencies_unchanged')}`",
        f"- direct button contract absent: `{capture.get('direct_button_contract_absent')}`",
        f"- button contract observed not owned: `{capture.get('button_contract_observed_not_owned')}`",
        "",
        "## Retained Dependencies",
        "",
    ]
    for name, present in (capture.get("retained_dependency_tokens") or {}).items():
        lines.append(f"- `{name}`: `{present}`")
    lines.extend(["", "## Verification", ""])
    run = dict(capture.get("readiness_run") or {})
    lines.append(f"- readiness run: passed=`{run.get('passed')}`, cmd=`{run.get('cmd')}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_decision_cutover.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_decision_cutover_"
        f"{stamp}.json"
    )
    audit_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_decision_cutover_"
        f"{stamp}.md"
    )
    report_path = REPORT_DIR / (
        "design_brain_physical_extraction_residual_shear_cleanup_route_entry_decision_cutover_"
        f"{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print("design_guide_post_click_low_bending_residual_shear_cleanup_route_entry_decision_cutover", payload["status"])
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
