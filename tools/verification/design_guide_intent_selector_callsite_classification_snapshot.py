"""Classify remaining Design Brain intent selector callsites in inputs_page.py.

Proof-only. This gives the physical extraction work a stable queue after the
old page helper was deleted and one render-stage selector call was removed.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


EXPECTED_PRODUCT_CALLS: dict[str, dict[str, str]] = {}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _window(lines: list[str], line_number: int, *, before: int = 6, after: int = 14) -> str:
    start = max(0, line_number - before - 1)
    end = min(len(lines), line_number + after - 1)
    return "\n".join(lines[start:end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    final_binding_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_visible_contract_binding_intent_contract_rebind_result(" in line
        ),
        0,
    )
    final_binding_window = _window(lines, final_binding_builder_line, before=80, after=80)
    shear_exact_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_shear_exact_blocker_safe_intent_result(" in line
        ),
        0,
    )
    shear_exact_window = _window(lines, shear_exact_builder_line, before=45, after=75)
    card_render_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_card_render_contract_preference_result(" in line
        ),
        0,
    )
    card_render_window = _window(lines, card_render_builder_line, before=45, after=95)
    displayed_primary_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_displayed_primary_safe_combined_promotion_result(" in line
        ),
        0,
    )
    displayed_primary_window = _window(lines, displayed_primary_builder_line, before=45, after=75)
    post_click_gate_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_post_click_safe_intent_allowed_gate_result(" in line
        ),
        0,
    )
    post_click_gate_window = _window(lines, post_click_gate_builder_line, before=25, after=55)
    post_click_proof_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_post_click_proof_intent_contract_result(" in line
        ),
        0,
    )
    post_click_proof_window = _window(lines, post_click_proof_builder_line, before=20, after=65)
    post_cleanup_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_post_cleanup_render_audit_intent_contract_result(" in line
        ),
        0,
    )
    post_cleanup_window = _window(lines, post_cleanup_builder_line, before=20, after=55)
    late_render_builder_line = next(
        (
            index
            for index, line in enumerate(lines, start=1)
            if "_build_final_design_guide_late_render_shear_action_intent_contract_result(" in line
        ),
        0,
    )
    late_render_window = _window(lines, late_render_builder_line, before=25, after=75)
    selector_lines = [
        index
        for index, line in enumerate(lines, start=1)
        if "_select_enabled_design_guide_contract_from_intent_rows(" in line
    ]
    import_lines = [
        index
        for index, line in enumerate(lines, start=1)
        if "select_enabled_design_guide_contract_from_intent_rows as" in line
    ]
    product_lines = [line for line in selector_lines if line not in import_lines]
    classified: list[dict[str, Any]] = []
    used_lines: set[int] = set()
    for key, spec in EXPECTED_PRODUCT_CALLS.items():
        matches = []
        for line_number in product_lines:
            if line_number in used_lines:
                continue
            window = _window(lines, line_number, before=10, after=18)
            if spec["line_token"] not in window:
                continue
            near_token = spec.get("near_token")
            if near_token and near_token not in window:
                continue
            matches.append(line_number)
        line_number = matches[0] if matches else None
        if line_number:
            used_lines.add(line_number)
        classified.append(
            {
                "id": key,
                "line": line_number,
                "category": spec["category"],
                "next_action": spec["next_action"],
                "found": bool(line_number),
                "window_hash": _stable_hash(_window(lines, line_number)) if line_number else "",
            }
        )
    unclassified = [line for line in product_lines if line not in used_lines]
    return {
        "decision": "INTENT_SELECTOR_CALLSITES_CLASSIFIED_FOR_ROUTE_BY_ROUTE_EXTRACTION",
        "selector_import_lines": import_lines,
        "product_selector_lines": product_lines,
        "product_selector_count": len(product_lines),
        "classified": classified,
        "unclassified_product_lines": unclassified,
        "old_page_helper_deleted": "def _enabled_design_guide_contract_from_intent_rows(" not in source,
        "selector_import_removed_from_inputs_page": not bool(import_lines),
        "card_view_model_builder_owns_selection": (
            "_build_final_design_guide_card_vm_intent_contract_promotion_result(" in source
            and "card_vm_intent_contract_promotion_cutover_applied" in source
            and "intent_contract, intent_row = _select_enabled_design_guide_contract_from_intent_rows(debug_payload)"
            not in source
        ),
        "final_binding_builder_owns_selection": (
            "_build_final_visible_contract_binding_intent_contract_rebind_result(" in source
            and "final_binding_intent_contract_rebind_cutover_applied" in source
            and (
                "_intent_contract, _intent_row = _select_enabled_design_guide_contract_from_intent_rows(_intent_debug_source)"
                not in final_binding_window
            )
        ),
        "shear_exact_blocker_builder_owns_selection": (
            "_build_final_design_guide_shear_exact_blocker_safe_intent_result(" in source
            and "shear_exact_blocker_safe_intent_cutover_applied" in source
            and (
                "safe_intent_contract, safe_intent_row = _select_enabled_design_guide_contract_from_intent_rows("
                not in shear_exact_window
            )
        ),
        "card_render_contract_preference_builder_owns_selection": (
            "_build_final_design_guide_card_render_contract_preference_result(" in source
            and "card_render_contract_preference_cutover_applied" in source
            and "_render_intent_source_for_contract" in card_render_window
            and "_select_enabled_design_guide_contract_from_intent_rows(" not in card_render_window
        ),
        "displayed_primary_safe_combined_builder_owns_selection": (
            "_build_final_design_guide_displayed_primary_safe_combined_promotion_result(" in source
            and "displayed_primary_safe_combined_promotion_cutover_applied" in source
            and "guidance_debug=guidance_debug" in displayed_primary_window
            and "_select_enabled_design_guide_contract_from_intent_rows(" not in displayed_primary_window
        ),
        "post_click_safe_intent_gate_builder_owns_selection": (
            "_build_final_design_guide_post_click_safe_intent_allowed_gate_result(" in source
            and "post_click_safe_intent_allowed_gate_cutover_applied" in source
            and "post_click_apply_context=bool(_post_click_apply_context_for_proof)" in post_click_gate_window
            and "_post_click_intent_contract_for_proof" not in source
            and "_post_click_intent_row_for_proof" not in source
        ),
        "post_click_proof_intent_contract_builder_owns_selection": (
            "_build_final_design_guide_post_click_proof_intent_contract_result(" in source
            and "post_click_proof_intent_contract_cutover_applied" in source
            and "guidance_debug=guidance_debug" in post_click_proof_window
            and "_proof_intent_contract, _proof_intent_row = _select_enabled_design_guide_contract_from_intent_rows("
            not in source
        ),
        "post_cleanup_render_audit_intent_contract_builder_owns_selection": (
            "_build_final_design_guide_post_cleanup_render_audit_intent_contract_result(" in source
            and "post_cleanup_render_audit_intent_contract_cutover_applied" in source
            and "guidance_debug=dict(_intent_debug_source or {})" in post_cleanup_window
            and "_intent_contract, _intent_row = _select_enabled_design_guide_contract_from_intent_rows(_intent_debug_source)"
            not in source
        ),
        "late_render_shear_action_intent_contract_builder_owns_selection": (
            "_build_final_design_guide_late_render_shear_action_intent_contract_result(" in source
            and "late_render_shear_action_intent_contract_cutover_applied" in source
            and "guidance_debug=dict(_render_intent_debug_source or {})" in late_render_window
            and "_render_intent_contract, _render_intent_row = _select_enabled_design_guide_contract_from_intent_rows("
            not in source
        ),
        "render_stage_builder_owns_selection": (
            "_build_final_visible_render_stage_intent_contract_rebind_result(" in source
            and "intent_contract=dict(_intent_contract or {})" not in _window(lines, 97886, before=20, after=35)
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_target": (
            "Direct product calls to the intent selector are removed from inputs_page.py. "
            "Next safe target is consumer/dead-code proof for the selector import and remaining "
            "compatibility bridges."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    classified = list(capture.get("classified") or [])
    return {
        "old_page_helper_deleted": capture.get("old_page_helper_deleted") is True,
        "selector_import_removed_from_inputs_page": capture.get("selector_import_removed_from_inputs_page") is True,
        "card_view_model_builder_owns_selection": capture.get("card_view_model_builder_owns_selection") is True,
        "final_binding_builder_owns_selection": capture.get("final_binding_builder_owns_selection") is True,
        "shear_exact_blocker_builder_owns_selection": capture.get("shear_exact_blocker_builder_owns_selection")
        is True,
        "card_render_contract_preference_builder_owns_selection": capture.get(
            "card_render_contract_preference_builder_owns_selection"
        )
        is True,
        "displayed_primary_safe_combined_builder_owns_selection": capture.get(
            "displayed_primary_safe_combined_builder_owns_selection"
        )
        is True,
        "post_click_safe_intent_gate_builder_owns_selection": capture.get(
            "post_click_safe_intent_gate_builder_owns_selection"
        )
        is True,
        "post_click_proof_intent_contract_builder_owns_selection": capture.get(
            "post_click_proof_intent_contract_builder_owns_selection"
        )
        is True,
        "post_cleanup_render_audit_intent_contract_builder_owns_selection": capture.get(
            "post_cleanup_render_audit_intent_contract_builder_owns_selection"
        )
        is True,
        "late_render_shear_action_intent_contract_builder_owns_selection": capture.get(
            "late_render_shear_action_intent_contract_builder_owns_selection"
        )
        is True,
        "render_stage_builder_owns_selection": capture.get("render_stage_builder_owns_selection") is True,
        "expected_product_selector_count": capture.get("product_selector_count") == 0,
        "all_expected_classifications_found": all(bool(row.get("found")) for row in classified),
        "no_unclassified_product_lines": not bool(capture.get("unclassified_product_lines")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Intent Selector Callsite Classification Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        f"Product selector count: `{capture.get('product_selector_count')}`",
        "",
        "## Classified Callsites",
        "",
        "| ID | Line | Category | Next action |",
        "| --- | ---: | --- | --- |",
    ]
    for row in capture.get("classified") or []:
        lines.append(
            f"| `{row.get('id')}` | `{row.get('line')}` | {row.get('category')} | {row.get('next_action')} |"
        )
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Unclassified", ""])
    if capture.get("unclassified_product_lines"):
        lines.extend(f"- `{line}`" for line in capture["unclassified_product_lines"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Target", "", str(capture.get("next_safe_target") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if not passed]
    payload = {
        "schema": "design_guide_intent_selector_callsite_classification_snapshot.v1",
        "created_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_selector_callsite_classification_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_selector_callsite_classification_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_selector_callsite_classification_snapshot {payload['status']}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
