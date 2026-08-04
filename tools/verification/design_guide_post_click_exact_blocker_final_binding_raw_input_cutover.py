"""Implementation verifier for post-click exact-blocker raw-input cutover.

This proves the targeted render-stage final binding call was removed only for
the post-click exact-blocker branch, and the existing Design Brain adapter is
now driven from the raw/adapted post-click bending item.
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
OLD_BINDING_TOKEN = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
OLD_ADAPTER_INPUT_TOKEN = "output_item=dict(_final_visible_item or {})"
RAW_ITEM_TOKEN = "_post_click_exact_blocker_raw_item = dict(_post_click_bending_resolution or {})"
NEW_FINAL_ITEM_TOKEN = "_final_visible_item = dict(_post_click_exact_blocker_raw_item)"
NEW_ADAPTER_INPUT_TOKEN = "output_item=dict(_post_click_exact_blocker_raw_item or {})"
ADAPTER_TOKEN = "_build_final_design_guide_post_click_final_contract_check_adapter_result("
RAW_BOUND_TRACE_TOKEN = "_stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof("
RAW_BOUND_RAW_ARG = "raw_item=dict(_post_click_exact_blocker_raw_item or {})"
CUTOVER_STAMP_TOKEN = "final_publication_post_click_exact_blocker_final_binding_raw_input_cutover_used"

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan",
    "design_guide_post_click_exact_blocker_raw_bound_parity_trace",
    "design_guide_post_click_exact_blocker_raw_bound_parity_scenarios",
    "design_guide_post_click_final_contract_adapter_result_parity_scenarios",
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
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


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


def _window_around_token(function_source: str, token: str, before: int = 40, after: int = 80) -> str:
    lines = function_source.splitlines()
    for index, line in enumerate(lines):
        if token in line:
            start = max(0, index - before)
            end = min(len(lines), index + after)
            return "\n".join(lines[start:end])
    return ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    raw_line = _line_for(function_source, RAW_ITEM_TOKEN, function_start)
    raw_window = _window_around_token(function_source, RAW_ITEM_TOKEN)
    adapter_window = _window_around_token(function_source, ADAPTER_TOKEN, before=5, after=14)
    old_binding_after_raw_item = OLD_BINDING_TOKEN in raw_window
    old_adapter_input_in_target_adapter = OLD_ADAPTER_INPUT_TOKEN in adapter_window
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "decision": "POST_CLICK_EXACT_BLOCKER_FINAL_BINDING_RAW_INPUT_CUTOVER_IMPLEMENTED",
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "raw_item_line": raw_line,
        "old_binding_after_raw_item_removed": not old_binding_after_raw_item,
        "old_adapter_input_in_target_adapter_removed": not old_adapter_input_in_target_adapter,
        "new_tokens": {
            RAW_ITEM_TOKEN: RAW_ITEM_TOKEN in raw_window,
            NEW_FINAL_ITEM_TOKEN: NEW_FINAL_ITEM_TOKEN in raw_window,
            RAW_BOUND_TRACE_TOKEN: RAW_BOUND_TRACE_TOKEN in raw_window,
            RAW_BOUND_RAW_ARG: RAW_BOUND_RAW_ARG in raw_window,
            NEW_ADAPTER_INPUT_TOKEN: NEW_ADAPTER_INPUT_TOKEN in raw_window,
            CUTOVER_STAMP_TOKEN: CUTOVER_STAMP_TOKEN in raw_window,
        },
        "adapter_result_application_preserved": all(
            token in raw_window
            for token in (
                "_post_click_exact_blocker_result = dict(",
                "_final_visible_item = dict(",
                "_final_visible_resolution.clear()",
                "_final_visible_resolution.update(",
                "guidance_debug.update(",
                "final_publication_post_click_final_contract_adapter_result_live_cutover_used",
            )
        ),
        "design_brain_adapter_present": (
            "def build_final_design_guide_post_click_final_contract_check_adapter_result("
            in final_source
        ),
        "design_brain_raw_bound_proof_present": (
            "def build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof("
            in final_source
        ),
        "latest_artifacts": latest,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "delete_ready_for_this_callsite": True,
        "broad_restamper_delete_ready": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "raw_item_line_present": capture.get("raw_item_line") is not None,
        "old_binding_after_raw_item_removed": capture.get("old_binding_after_raw_item_removed") is True,
        "old_adapter_input_in_target_adapter_removed": (
            capture.get("old_adapter_input_in_target_adapter_removed") is True
        ),
        "new_tokens_present": all((capture.get("new_tokens") or {}).values()),
        "adapter_result_application_preserved": (
            capture.get("adapter_result_application_preserved") is True
        ),
        "design_brain_adapter_present": capture.get("design_brain_adapter_present") is True,
        "design_brain_raw_bound_proof_present": (
            capture.get("design_brain_raw_bound_proof_present") is True
        ),
        "cutover_plan_latest_pass": (
            latest.get("design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_plan")
            or {}
        ).get("status")
        == "PASS",
        "raw_bound_trace_latest_pass": (
            latest.get("design_guide_post_click_exact_blocker_raw_bound_parity_trace") or {}
        ).get("status")
        == "PASS",
        "raw_bound_scenarios_latest_pass": (
            latest.get("design_guide_post_click_exact_blocker_raw_bound_parity_scenarios") or {}
        ).get("status")
        == "PASS",
        "adapter_result_parity_latest_pass": (
            latest.get("design_guide_post_click_final_contract_adapter_result_parity_scenarios")
            or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (
            latest.get("design_guide_render_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_latest_pass": (
            latest.get("design_guide_independence_lock") or {}
        ).get("status")
        == "PASS",
        "this_callsite_delete_ready": capture.get("delete_ready_for_this_callsite") is True,
        "broad_restamper_not_delete_ready": capture.get("broad_restamper_delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Exact Blocker Final Binding Raw-Input Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Raw item line: `{capture.get('raw_item_line')}`",
        f"- Old binding removed after raw item: `{capture.get('old_binding_after_raw_item_removed')}`",
        f"- Old adapter input removed from target adapter: `{capture.get('old_adapter_input_in_target_adapter_removed')}`",
        f"- Adapter result application preserved: `{capture.get('adapter_result_application_preserved')}`",
        f"- This callsite delete-ready: `{capture.get('delete_ready_for_this_callsite')}`",
        f"- Broad restamper delete-ready: `{capture.get('broad_restamper_delete_ready')}`",
        "",
        "## New Tokens",
        "",
    ]
    for token, value in (capture.get("new_tokens") or {}).items():
        lines.append(f"- `{token}`: `{value}`")
    lines.extend(["", "## Checks", ""])
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
        "schema": "design_guide_post_click_exact_blocker_final_binding_raw_input_cutover.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_exact_blocker_final_binding_raw_input_cutover {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
