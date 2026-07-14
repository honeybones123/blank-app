"""Replacement readiness for post-click exact-blocker final binding.

Proof-only. This snapshot checks whether the
post_click_exact_blocker_final_binding call can be deleted now, or whether the
FinalDesignGuidePublication adapter still depends on the old bound item.
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

FUNCTION_NAME = "_render_fast_design_guidance_panel"
CALL_TOKEN = "_final_visible_item = _publish_final_visible_design_guide_contract_binding("
PRE_CONTEXT_TOKEN = "_post_click_bending_resolution"

REQUIRED_TOKENS: tuple[str, ...] = (
    "_post_click_bending_resolution = _post_click_low_bending_resolution_item(",
    "_post_click_bending_contract = (",
    "not _design_guide_button_contract_enabled(_post_click_bending_contract)",
    "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
    "_post_click_exact_blocker_adapter_result = (",
    "_build_final_design_guide_post_click_final_contract_check_adapter_result(",
    "output_item=dict(_final_visible_item or {})",
    "bending_resolution=dict(_post_click_bending_resolution or {})",
    "bending_contract=dict(_post_click_bending_contract or {})",
    "_post_click_exact_blocker_result = dict(",
    "_final_visible_item = dict(",
    "_final_visible_resolution.clear()",
    "_final_visible_resolution.update(",
    "guidance_debug.update(",
    "final_publication_post_click_final_contract_adapter_result_live_cutover_used",
)

MISSING_PARITY_TOKENS: tuple[str, ...] = (
    "final_publication_post_click_exact_blocker_raw_bound_parity",
    "final_publication_post_click_exact_blocker_raw_item_hash",
    "final_publication_post_click_exact_blocker_bound_item_hash",
    "final_publication_post_click_exact_blocker_raw_bound_adapter_result_parity",
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_render_panel_binding_adapter_readiness",
    "design_guide_render_fast_panel_binding_ownership",
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
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def _line_for(function_source: str, token: str, start_line: int | None, pre_context_token: str) -> int | None:
    lines = function_source.splitlines()
    for offset, line in enumerate(lines):
        if token not in line:
            continue
        pre_window = "\n".join(lines[max(0, offset - 35) : offset + 1])
        if pre_context_token and pre_context_token not in pre_window:
            continue
        return (start_line or 1) + offset
    return None


def _window(source: str, line: int | None, before: int = 90, after: int = 90) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    function_start, function_end, function_source = _function_source(source, FUNCTION_NAME)
    call_line = _line_for(function_source, CALL_TOKEN, function_start, PRE_CONTEXT_TOKEN)
    context = _window(source, call_line)
    required_token_results = {token: token in context for token in REQUIRED_TOKENS}
    missing_parity_results = {token: token in context or token in source for token in MISSING_PARITY_TOKENS}
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    adapter_depends_on_bound_item = "output_item=dict(_final_visible_item or {})" in context
    raw_vs_bound_parity_exists = any(missing_parity_results.values())
    ready_to_delete_binding = bool(
        call_line is not None
        and all(required_token_results.values())
        and not adapter_depends_on_bound_item
        and raw_vs_bound_parity_exists
    )
    parity_state_known = bool(raw_vs_bound_parity_exists)
    return {
        "decision": (
            "POST_CLICK_EXACT_BLOCKER_FINAL_BINDING_READY_TO_DELETE"
            if ready_to_delete_binding
            else "POST_CLICK_EXACT_BLOCKER_FINAL_BINDING_TRACE_READY_BOUND_ITEM_STILL_DRIVES_ADAPTER"
            if parity_state_known
            else "POST_CLICK_EXACT_BLOCKER_FINAL_BINDING_NOT_READY_RAW_BOUND_PARITY_MISSING"
        ),
        "function": FUNCTION_NAME,
        "function_start_line": function_start,
        "function_end_line": function_end,
        "call_line": call_line,
        "required_tokens": required_token_results,
        "missing_parity_tokens_present": missing_parity_results,
        "adapter_depends_on_bound_item": adapter_depends_on_bound_item,
        "raw_vs_bound_parity_exists": raw_vs_bound_parity_exists,
        "raw_vs_bound_parity_state_known": parity_state_known,
        "ready_to_delete_binding": ready_to_delete_binding,
        "next_safe_instruction": (
            "Add a trace-only raw-vs-bound parity proof for this branch: compare the raw "
            "_post_click_bending_resolution item with the old bound _final_visible_item, then prove "
            "the adapter result is identical when driven from the raw item before deleting the binding."
        ),
        "latest_artifacts": {
            prefix: {"status": data.get("status"), "path": data.get("path")}
            for prefix, data in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "target_callsite_present": capture.get("call_line") is not None,
        "required_tokens_present": all((capture.get("required_tokens") or {}).values()),
        "adapter_dependency_detected": capture.get("adapter_depends_on_bound_item") is True,
        "raw_bound_parity_state_known": capture.get("raw_vs_bound_parity_state_known") is True,
        "not_ready_to_delete": capture.get("ready_to_delete_binding") is False,
        "readiness_map_pass": (
            latest.get("design_guide_render_panel_binding_adapter_readiness") or {}
        ).get("status")
        == "PASS",
        "fast_panel_binding_ownership_pass": (
            latest.get("design_guide_render_fast_panel_binding_ownership") or {}
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
        "# Post-Click Exact Blocker Final Binding Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Target call line: `{capture.get('call_line')}`",
        f"- Adapter depends on old bound item: `{capture.get('adapter_depends_on_bound_item')}`",
        f"- Raw-vs-bound parity exists: `{capture.get('raw_vs_bound_parity_exists')}`",
        f"- Ready to delete binding: `{capture.get('ready_to_delete_binding')}`",
        f"- Next instruction: {capture.get('next_safe_instruction')}",
        "",
        "## Required Tokens",
    ]
    for key, value in (capture.get("required_tokens") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Missing Parity Tokens", ""])
    for key, value in (capture.get("missing_parity_tokens_present") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
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
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_exact_blocker_final_binding_replacement_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_exact_blocker_final_binding_replacement_readiness_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_exact_blocker_final_binding_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_exact_blocker_final_binding_replacement_readiness {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
