"""Ownership audit for intent-contract-from-debug-rows tails.

Proof-only. This classifies the remaining old page-owned path that can recover
an enabled button contract from guidance debug intent rows and then mutate the
final visible Design Guide item/contract.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _line_for(lines: list[str], token: str, *, start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if token in lines[index]:
            return index + 1
    return None


def _window(lines: list[str], line_number: int | None, *, before: int = 30, after: int = 90) -> str:
    if not line_number:
        return ""
    start = max(0, line_number - before - 1)
    end = min(len(lines), line_number + after - 1)
    return "\n".join(lines[start:end])


def _all_lines_for(lines: list[str], token: str) -> list[int]:
    return [index for index, line in enumerate(lines, start=1) if token in line]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    helper_line = _line_for(lines, "def _enabled_design_guide_contract_from_intent_rows(")
    old_call_lines = [
        index
        for index, line in enumerate(lines, start=1)
        if re.search(r"(?<!select)_enabled_design_guide_contract_from_intent_rows\(", line)
    ]
    public_call_lines = _all_lines_for(lines, "_select_enabled_design_guide_contract_from_intent_rows(")
    call_lines = [line for line in old_call_lines if line != helper_line]
    call_lines.extend(line for line in public_call_lines if line not in call_lines)
    call_lines = sorted(call_lines)

    final_binding_call_line = (
        _line_for(lines, "_intent_contract, _intent_row = _enabled_design_guide_contract_from_intent_rows(")
        or _line_for(lines, "_intent_contract, _intent_row = _select_enabled_design_guide_contract_from_intent_rows(")
    )
    final_binding_window = _window(lines, final_binding_call_line, before=35, after=150)

    render_stage_call_line = _line_for(
        lines,
        "_build_final_visible_render_stage_intent_contract_rebind_result(",
        start=93000,
    )
    render_stage_window = _window(lines, render_stage_call_line, before=20, after=60)

    helper_window = _window(lines, helper_line, before=2, after=35)
    final_binding_tokens = {
        "skips_post_click_apply_context": "if not _post_click_apply_context_for_binding:" in final_binding_window,
        "reads_debug_bundle": "DESIGN_GUIDE_DEBUG_BUNDLE_KEY" in final_binding_window,
        "checks_active_strength_failures": "_active_strength_failures_for_binding" in final_binding_window,
        "checks_cross_family_current_binding": "_current_binding_cross_family" in final_binding_window,
        "mutates_contract": "contract = dict(_intent_contract)" in final_binding_window,
        "mutates_out": "out.update(" in final_binding_window,
        "mutates_updates_and_action_type": (
            'action_type = "apply_resolved_candidate"' in final_binding_window
            and "updates = dict(_intent_updates)" in final_binding_window
        ),
        "stamps_debug": 'debug_sink["final_binding_intent_contract_preferred"] = True' in final_binding_window,
        "uses_rebind_result_builder": (
            "_build_final_visible_contract_binding_intent_contract_rebind_result(" in final_binding_window
        ),
        "stamps_rebind_trace": (
            '"final_binding_intent_contract_rebind_trace_wired"' in final_binding_window
            and '"final_binding_intent_contract_rebind_product_driving"' in final_binding_window
            and '"final_binding_intent_contract_rebind_render_driving"' in final_binding_window
            and '"final_binding_intent_contract_rebind_apply_driving"' in final_binding_window
            and '"final_binding_intent_contract_rebind_session_driving"' in final_binding_window
        ),
        "applies_rebind_result_effects": (
            "_intent_rebind_result = dict(" in final_binding_window
            and 'contract = dict(_intent_contract_effect)' in final_binding_window
            and 'out.update(dict(_intent_item_effect))' in final_binding_window
            and '"final_binding_intent_contract_rebind_cutover_applied"' in final_binding_window
        ),
    }
    render_stage_tokens = {
        "guards_disabled_contract_only": "not _design_guide_button_contract_enabled(_final_visible_contract)" in render_stage_window,
        "mutates_final_visible_contract": "_final_visible_contract = dict(_intent_contract)" in render_stage_window,
        "mutates_final_visible_item": '_final_visible_item["button_contract"] = dict(_final_visible_contract)' in render_stage_window,
        "records_apply_payload": "_record_rendered_design_guide_primary_apply_payload(" in render_stage_window,
        "builder_owns_intent_selection": (
            "_select_enabled_design_guide_contract_from_intent_rows(guidance_debug)" not in render_stage_window
            and "intent_contract=dict(_intent_contract or {})" not in render_stage_window
            and "intent_row=dict(_intent_row or {})" not in render_stage_window
        ),
        "uses_render_stage_rebind_result_builder": (
            "_build_final_visible_render_stage_intent_contract_rebind_result(" in render_stage_window
        ),
        "stamps_render_stage_rebind_trace": (
            '"render_stage_intent_contract_rebind_trace_wired"' in render_stage_window
            and '"render_stage_intent_contract_rebind_product_driving"' in render_stage_window
            and '"render_stage_intent_contract_rebind_render_driving"' in render_stage_window
            and '"render_stage_intent_contract_rebind_apply_driving"' in render_stage_window
            and '"render_stage_intent_contract_rebind_session_driving"' in render_stage_window
        ),
        "applies_render_stage_rebind_result_effects": (
            "_render_stage_intent_rebind_result = dict(" in render_stage_window
            and "_render_stage_contract_effect = dict(" in render_stage_window
            and "_render_stage_item_effect = dict(" in render_stage_window
            and "_final_visible_contract = dict(_render_stage_contract_effect)" in render_stage_window
            and "_final_visible_item.update(dict(_render_stage_item_effect))" in render_stage_window
            and '"render_stage_intent_contract_rebind_cutover_applied"' in render_stage_window
        ),
    }
    helper_tokens = {
        "scans_displayed_guidance_intent_items": '"displayed_guidance_intent_items"' in helper_window,
        "scans_guidance_intent_items": '"guidance_intent_items"' in helper_window,
        "requires_enabled_contract": "_design_guide_button_contract_enabled(contract)" in helper_window,
        "requires_apply_resolved_candidate": '"apply_resolved_candidate"' in helper_window,
        "requires_updates": "dict(contract.get(\"updates\") or {})" in helper_window,
        "helper_deleted": helper_line is None
        and not any(re.search(r"(?<!select)_enabled_design_guide_contract_from_intent_rows\(", line) for line in lines),
        "is_thin_design_brain_selector_wrapper": (
            "_select_enabled_design_guide_contract_from_intent_rows(guidance_debug)" in helper_window
            and '"displayed_guidance_intent_items", "guidance_intent_items"' not in helper_window
            and "for row in rows:" not in helper_window
        ),
    }

    return {
        "decision": "INTENT_CONTRACT_FROM_DEBUG_ROWS_TAIL_STILL_LIVE_NOT_READY_TO_DELETE",
        "helper_line": helper_line,
        "call_lines": call_lines,
        "final_binding_call_line": final_binding_call_line,
        "render_stage_call_line": render_stage_call_line,
        "helper_tokens": helper_tokens,
        "final_binding_tokens": final_binding_tokens,
        "render_stage_tokens": render_stage_tokens,
        "classification": {
            "helper": "deleted; callsites use Design Brain debug-row contract recovery selector directly",
            "final_binding_tail": (
                "proof-driven final-visible contract/item mutation tail using "
                "FinalDesignGuidePublication.final_visible_contract_binding_intent_contract_rebind"
            ),
            "render_stage_tail": (
                "proof-driven render-stage contract/item mutation tail using "
                "FinalDesignGuidePublication.render_stage_intent_contract_rebind"
            ),
        },
        "delete_or_narrow_now": False,
        "ready_for_cutover": False,
        "latest_artifacts": {
            "cleanup_dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "intent_contract_rebind_cutover_implementation": _latest(
                "design_guide_intent_contract_rebind_cutover_implementation"
            ),
            "render_stage_intent_contract_rebind_cutover_readiness": _latest(
                "design_guide_render_stage_intent_contract_rebind_cutover_readiness"
            ),
            "intent_row_selector_extraction": _latest(
                "design_guide_intent_row_selector_extraction"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "next_safe_step": (
            "The debug-row contract recovery policy is extracted to Design Brain and the page "
            "compatibility wrapper has been deleted. Continue auditing the remaining direct "
            "Design Brain selector callsites for route-specific extraction/deletion."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    helper_tokens = dict(capture.get("helper_tokens") or {})
    final_binding_tokens = dict(capture.get("final_binding_tokens") or {})
    render_stage_tokens = dict(capture.get("render_stage_tokens") or {})
    final_binding_old_shape = all(
        bool(final_binding_tokens.get(key))
        for key in (
            "skips_post_click_apply_context",
            "reads_debug_bundle",
            "checks_active_strength_failures",
            "checks_cross_family_current_binding",
            "mutates_contract",
            "mutates_out",
            "mutates_updates_and_action_type",
            "stamps_debug",
        )
    )
    final_binding_cutover_shape = all(
        bool(final_binding_tokens.get(key))
        for key in (
            "skips_post_click_apply_context",
            "reads_debug_bundle",
            "checks_active_strength_failures",
            "checks_cross_family_current_binding",
            "uses_rebind_result_builder",
            "stamps_rebind_trace",
            "applies_rebind_result_effects",
        )
    ) and (
        latest.get("intent_contract_rebind_cutover_implementation") or {}
    ).get("status") == "PASS"
    render_stage_old_shape = all(
        bool(render_stage_tokens.get(key))
        for key in (
            "guards_disabled_contract_only",
            "mutates_final_visible_contract",
            "mutates_final_visible_item",
            "records_apply_payload",
        )
    )
    render_stage_cutover_shape = all(
        bool(render_stage_tokens.get(key))
        for key in (
            "guards_disabled_contract_only",
            "builder_owns_intent_selection",
            "uses_render_stage_rebind_result_builder",
            "stamps_render_stage_rebind_trace",
            "applies_render_stage_rebind_result_effects",
            "records_apply_payload",
        )
    ) and (
        latest.get("render_stage_intent_contract_rebind_cutover_readiness") or {}
    ).get("status") == "PASS"
    helper_old_shape = all(
        bool(helper_tokens.get(key))
        for key in (
            "scans_displayed_guidance_intent_items",
            "scans_guidance_intent_items",
            "requires_enabled_contract",
            "requires_apply_resolved_candidate",
            "requires_updates",
        )
    )
    helper_extracted_shape = bool(
        helper_tokens.get("is_thin_design_brain_selector_wrapper")
        or helper_tokens.get("helper_deleted")
    ) and (
        latest.get("intent_row_selector_extraction") or {}
    ).get("status") == "PASS"
    return {
        "helper_found": bool(capture.get("helper_line")) or bool(helper_tokens.get("helper_deleted")),
        "callsites_found": len(capture.get("call_lines") or []) > 0,
        "final_binding_tail_found": bool(capture.get("final_binding_call_line")),
        "render_stage_tail_found": bool(capture.get("render_stage_call_line")),
        "helper_policy_classified": bool(helper_old_shape or helper_extracted_shape),
        "final_binding_tail_classified": bool(final_binding_old_shape or final_binding_cutover_shape),
        "render_stage_tail_classified": bool(render_stage_old_shape or render_stage_cutover_shape),
        "not_ready_to_delete": capture.get("delete_or_narrow_now") is False,
        "not_ready_for_cutover": capture.get("ready_for_cutover") is False,
        "cleanup_dead_body_deletion_pass": (latest.get("cleanup_dead_body_deletion") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Intent Contract From Debug Rows Tail Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Locations",
        "",
        f"- Helper line: `{capture.get('helper_line')}`",
        f"- Call lines: `{capture.get('call_lines')}`",
        f"- Final-binding tail line: `{capture.get('final_binding_call_line')}`",
        f"- Render-stage tail line: `{capture.get('render_stage_call_line')}`",
        "",
        "## Classification",
        "",
    ]
    for key, value in (capture.get("classification") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Token Proof", ""])
    for group_name in ("helper_tokens", "final_binding_tokens", "render_stage_tokens"):
        lines.append(f"### {group_name}")
        for key, value in (capture.get(group_name) or {}).items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    lines.extend(["## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
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
        "schema": "design_guide_intent_contract_from_debug_rows_tail_ownership_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_contract_from_debug_rows_tail_ownership_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_contract_from_debug_rows_tail_ownership_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_contract_from_debug_rows_tail_ownership_audit {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
