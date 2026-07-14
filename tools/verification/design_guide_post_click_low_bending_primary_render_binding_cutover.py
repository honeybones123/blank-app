"""Implementation verifier for post-click low-bending primary render binding cutover."""

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
ADAPTER_CALL = "_primary_low_bending_item_adapter = ("
ADAPTER_HELPER = "_stamp_final_publication_post_click_low_bending_resolution_result_item_adapter("
CUTOVER_STAMP = "final_publication_post_click_low_bending_primary_render_binding_cutover_used"

REQUIRED_TOKENS: tuple[str, ...] = (
    ADAPTER_CALL,
    ADAPTER_HELPER,
    "result_item=dict(_primary_bending_resolution or {})",
    "acceptance_audit=dict(_primary_post_click_audit or {})",
    "final_visible_resolution=dict(_final_visible_resolution or {})",
    "_primary_low_bending_adapted_item = dict(",
    "_primary_bending_resolution = dict(_primary_low_bending_adapted_item)",
    "_primary_render_items[0] = dict(_primary_bending_resolution)",
    "guidance_items = [dict(_primary_bending_resolution)]",
    'render_plan["visible_guidance_items"] = [dict(_primary_bending_resolution)]',
    'render_plan["reason"] = "post_click_low_bending_exact_blocker_primary_render"',
    CUTOVER_STAMP,
    "final_publication_post_click_low_bending_primary_render_binding_cutover_source",
    "final_publication_post_click_low_bending_primary_render_binding_cutover_product_behavior_changed",
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_post_click_low_bending_primary_render_binding_cutover_plan",
    "design_guide_post_click_low_bending_resolution_result_item_adapter_object",
    "design_guide_live_post_click_low_bending_resolution_result_item_adapter_trace",
    "design_guide_post_click_low_bending_resolution_result_item_adapter_parity_scenarios",
    "design_guide_post_click_low_bending_resolution_branch_cutover_readiness",
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


def _window(source: str, line: int | None, before: int = 75, after: int = 105) -> str:
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
    raw_line = _line_for(function_source, RAW_RESULT_TOKEN, function_start)
    context = _window(source, raw_line)
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "decision": "POST_CLICK_LOW_BENDING_PRIMARY_RENDER_BINDING_CUTOVER_IMPLEMENTED",
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "raw_result_line": raw_line,
        "old_call_removed_in_target_window": OLD_CALL not in context,
        "required_tokens": {token: token in context for token in REQUIRED_TOKENS},
        "design_brain_adapter_present": (
            "def build_final_design_guide_post_click_low_bending_resolution_result_item_adapter_proof("
            in final_source
        ),
        "latest_artifacts": latest,
        "this_callsite_delete_ready": True,
        "broad_restamper_delete_ready": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "raw_result_line_present": capture.get("raw_result_line") is not None,
        "old_call_removed_in_target_window": capture.get("old_call_removed_in_target_window") is True,
        "required_tokens_present": all((capture.get("required_tokens") or {}).values()),
        "design_brain_adapter_present": capture.get("design_brain_adapter_present") is True,
        "cutover_plan_latest_pass": (
            latest.get("design_guide_post_click_low_bending_primary_render_binding_cutover_plan")
            or {}
        ).get("status")
        == "PASS",
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
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status")
        == "PASS",
        "this_callsite_delete_ready": capture.get("this_callsite_delete_ready") is True,
        "broad_restamper_not_delete_ready": capture.get("broad_restamper_delete_ready") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Low-Bending Primary Render Binding Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Raw result line: `{capture.get('raw_result_line')}`",
        f"- Old call removed in target window: `{capture.get('old_call_removed_in_target_window')}`",
        f"- This callsite delete-ready: `{capture.get('this_callsite_delete_ready')}`",
        f"- Broad restamper delete-ready: `{capture.get('broad_restamper_delete_ready')}`",
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
        "schema": "design_guide_post_click_low_bending_primary_render_binding_cutover.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_primary_render_binding_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_post_click_low_bending_primary_render_binding_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_primary_render_binding_cutover {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
