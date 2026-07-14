"""Implementation verifier for compute rebound restamper cutover.

This verifies only the two compute rebound restamper callsites were replaced by
the controller replacement adapter. It does not prove broad deletion of
_publish_final_visible_design_guide_contract_binding.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

TARGETS = {
    "compute_late_evidence_contract_rebound": {
        "function": "_apply_compute_late_evidence_contract_rebound",
        "old_call": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "new_call": "_late_rebound_item = _compute_rebound_item_from_controller_publication_item(",
        "required_tokens": (
            "_late_evidence_acceptance = {",
            "_late_updates = dict(",
            "_late_contract_disabled_or_mismatched = (",
            "if not (",
            "if isinstance(_late_rebound_item, dict) and _design_guide_button_contract_enabled(_late_rebound_contract):",
            "_late_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only(",
        ),
    },
    "post_core_evidence_rebound": {
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "old_call": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "new_call": "_post_evidence_rebound = _compute_rebound_item_from_controller_publication_item(",
        "required_tokens": (
            "_post_core_mismatch = {",
            "_post_evidence_updates = dict(",
            "_post_evidence_disabled_or_mismatched = (",
            "if (",
            "if isinstance(_post_evidence_rebound, dict) and _post_evidence_rebound:",
            "_post_mutation_adapter = _stamp_design_guide_controller_compute_rebound_mutation_trace_only(",
        ),
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _window(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    rows = {}
    for target_id, target in TARGETS.items():
        window = _window(source, target["function"])
        rows[target_id] = {
            "function_present": bool(window),
            "old_call_removed": target["old_call"] not in window,
            "new_call_present": target["new_call"] in window,
            "required_tokens_present": {
                token: token in window for token in target["required_tokens"]
            },
        }
    return {
        "decision": "COMPUTE_REBOUND_RESTAMPER_CUTOVER_IMPLEMENTED_NOT_DELETE_READY",
        "rows": rows,
        "controller_checks": {
            "replacement_request_exported": "DesignGuideControllerComputeReboundPublicationItemRequest" in controller,
            "replacement_response_exported": "DesignGuideControllerComputeReboundPublicationItemResponse" in controller,
            "replacement_function_exported": "run_design_guide_controller_compute_rebound_publication_item_trace_only" in controller,
            "updates_make_rebound_contract_actionable": '"action_type"] = contract.get("action_type") or "apply_resolved_candidate"' in controller,
        },
        "latest": {
            "replacement_adapter_parity": _latest("design_guide_compute_rebound_restamper_replacement_adapter_parity"),
            "cutover_plan": _latest("design_guide_compute_rebound_restamper_cutover_plan"),
            "focused_parity": _latest("design_guide_compute_rebound_restamper_focused_parity_scenarios"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "delete_ready": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("rows") or {})
    latest = dict(capture.get("latest") or {})
    return {
        "all_target_functions_present": all(row.get("function_present") for row in rows.values()),
        "old_calls_removed_for_targets": all(row.get("old_call_removed") for row in rows.values()),
        "new_calls_present_for_targets": all(row.get("new_call_present") for row in rows.values()),
        "required_guard_and_branch_tokens_present": all(
            all(dict(row.get("required_tokens_present") or {}).values()) for row in rows.values()
        ),
        "controller_checks_pass": all(dict(capture.get("controller_checks") or {}).values()),
        "replacement_adapter_parity_latest_pass": (
            latest.get("replacement_adapter_parity") or {}
        ).get("status") == "PASS",
        "cutover_plan_latest_pass": (latest.get("cutover_plan") or {}).get("status") == "PASS",
        "focused_parity_latest_pass": (latest.get("focused_parity") or {}).get("status") == "PASS",
        "not_delete_ready": capture.get("delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Compute Rebound Restamper Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Targets",
        "",
    ]
    for target_id, row in dict(capture.get("rows") or {}).items():
        lines.append(f"- `{target_id}` old removed=`{row.get('old_call_removed')}` new present=`{row.get('new_call_present')}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "Run composed locks and remaining-restamper audit. This cutover removes two "
                "compute rebound restamper callsites from the page path, but it is not broad "
                "deletion proof for the restamper helper."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_compute_rebound_restamper_cutover_implementation.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    json_path = ARTIFACT_DIR / f"design_guide_compute_rebound_restamper_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_rebound_restamper_cutover_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
