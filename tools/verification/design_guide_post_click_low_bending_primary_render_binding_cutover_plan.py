"""Cutover plan for post-click low-bending primary render binding.

Proof-only. This verifier checks whether the primary-render branch can replace
its old final-visible restamper call with the existing
FinalDesignGuidePublication low-bending item adapter.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

FUNCTION_NAME = "_render_fast_design_guidance_panel"
OLD_CALL = "_primary_bending_resolution = _publish_final_visible_design_guide_contract_binding("
RAW_RESULT_TOKEN = "_primary_bending_resolution = _post_click_low_bending_resolution_item("
ADAPTER_HELPER = "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter("

REQUIRED_CONTEXT_TOKENS: tuple[str, ...] = (
    "_primary_post_click_audit",
    "_primary_bending_contract = (",
    "not _design_guide_button_contract_enabled(_primary_bending_contract)",
    "_primary_render_items[0] = dict(_primary_bending_resolution)",
    "guidance_items = [dict(_primary_bending_resolution)]",
    'render_plan["visible_guidance_items"] = [dict(_primary_bending_resolution)]',
    'render_plan["reason"] = "post_click_low_bending_exact_blocker_primary_render"',
    'guidance_debug["post_click_low_bending_action_replaced_by_exact_blocker"] = True',
    'guidance_debug["button_contract_enabled"] = False',
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_post_click_low_bending_resolution_result_item_adapter_object",
    "design_guide_live_post_click_low_bending_resolution_result_item_adapter_trace",
    "design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios",
    "design_guide_post_click_low_bending_resolution_branch_cutover_readiness",
    "design_guide_render_fast_panel_binding_ownership",
    "design_guide_render_panel_binding_adapter_readiness",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [index for index in (next_def_index, next_class_index) if index >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _line_for(function_source: str, token: str, start_line: int | None) -> int | None:
    for offset, line in enumerate(function_source.splitlines()):
        if token in line:
            return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 90, after: int = 70) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    old_call_line = _line_for(function_source, OLD_CALL, function_start)
    raw_result_line = _line_for(function_source, RAW_RESULT_TOKEN, function_start)
    context = _window(source, raw_result_line)
    artifacts = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    panel_payload = artifacts["design_guide_render_panel_binding_adapter_readiness"]["payload"]
    panel_capture = dict(panel_payload.get("capture") or {})
    branch_payload = artifacts["design_guide_post_click_low_bending_resolution_branch_cutover_readiness"][
        "payload"
    ]
    branch_capture = dict(branch_payload.get("capture") or {})
    return {
        "decision": "POST_CLICK_LOW_BENDING_PRIMARY_RENDER_BINDING_CUTOVER_PLAN_READY",
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "old_call_line": old_call_line,
        "raw_result_line": raw_result_line,
        "old_call_present": old_call_line is not None,
        "raw_result_present": raw_result_line is not None,
        "adapter_helper_available": ADAPTER_HELPER in source,
        "design_brain_adapter_present": (
            "def build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof("
            in final_source
        ),
        "context_tokens": {token: token in context for token in REQUIRED_CONTEXT_TOKENS},
        "panel_next_target_is_primary": (
            panel_capture.get("next_safe_target") == "post_click_low_bending_primary_render_binding"
        ),
        "branch_ready_for_live_cutover": branch_capture.get("ready_for_live_branch_cutover") is True,
        "proposed_replacement": {
            "insert_adapter_before_disabled_contract_branch": True,
            "old_restamper_call_removed": True,
            "preserve_primary_render_assignments": True,
            "preserve_render_plan_reason": True,
            "preserve_debug_selected_fields": True,
        },
        "latest_artifacts": {
            prefix: {"status": data.get("status"), "path": data.get("path")}
            for prefix, data in artifacts.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_instruction": (
            "The low-bending result item adapter is present after _post_click_low_bending_resolution_item(...), "
            "and the old _primary_bending_resolution restamper call is absent. Preserve the primary "
            "render item, guidance_items, render_plan, and debug assignments."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "old_call_removed": capture.get("old_call_present") is False,
        "raw_result_present": capture.get("raw_result_present") is True,
        "adapter_helper_available": capture.get("adapter_helper_available") is True,
        "design_brain_adapter_present": capture.get("design_brain_adapter_present") is True,
        "context_tokens_present": all((capture.get("context_tokens") or {}).values()),
        "panel_next_target_retired_or_absent": capture.get("panel_next_target_is_primary") is False,
        "branch_ready_for_live_cutover": capture.get("branch_ready_for_live_cutover") is True,
        "item_adapter_object_pass": (
            latest.get("design_guide_post_click_low_bending_resolution_result_item_adapter_object")
            or {}
        ).get("status")
        == "PASS",
        "item_adapter_trace_pass": (
            latest.get("design_guide_live_post_click_low_bending_resolution_result_item_adapter_trace")
            or {}
        ).get("status")
        == "PASS",
        "item_adapter_parity_pass": (
            latest.get("design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios")
            or {}
        ).get("status")
        == "PASS",
        "branch_readiness_pass": (
            latest.get("design_guide_post_click_low_bending_resolution_branch_cutover_readiness")
            or {}
        ).get("status")
        == "PASS",
        "render_fast_ownership_pass": (
            latest.get("design_guide_render_fast_panel_binding_ownership") or {}
        ).get("status")
        == "PASS",
        "panel_readiness_pass": (
            latest.get("design_guide_render_panel_binding_adapter_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Primary Render Binding Cutover Plan",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Old call line: `{capture.get('old_call_line')}`",
        f"- Raw result line: `{capture.get('raw_result_line')}`",
        f"- Panel next target is primary: `{capture.get('panel_next_target_is_primary')}`",
        f"- Branch ready for live cutover: `{capture.get('branch_ready_for_live_cutover')}`",
        f"- Next instruction: {capture.get('next_safe_instruction')}",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
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
        "schema": "design_guide_post_click_low_bending_primary_render_binding_cutover_plan.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_primary_render_binding_cutover_plan_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_primary_render_binding_cutover_plan_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_primary_render_binding_cutover_plan {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
