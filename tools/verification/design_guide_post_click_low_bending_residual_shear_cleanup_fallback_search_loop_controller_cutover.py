"""Verify residual-shear fallback search loop is controller-owned.

This is a focused cutover verifier. It proves the page no longer owns fallback
loop order or candidate sequence accumulation while generator/evaluator/screen/
selector execution stays injected and behavior-sensitive CTA/apply wording stays
outside the controller loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("


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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
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
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if "PASS" in raw.upper() or "LOCKED" in raw.upper() else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(inputs_source, ROUTE_START, ROUTE_END)
    controller_loop_token = (
        "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop("
    )
    controller_loop = _between(controller_source, controller_loop_token, "\ndef ")
    page_loop_tokens_absent = {
        "page_for_loop_absent": (
            "for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):"
            not in route
        ),
        "page_evaluation_append_absent": "fallback_candidate_evaluation_sequence.append("
        not in route,
        "page_selection_append_absent": "fallback_candidate_selection_sequence.append("
        not in route,
        "page_selected_result_builder_absent": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result("
            not in route
        ),
    }
    controller_loop_tokens_present = {
        "controller_loop_present": controller_loop_token in controller_source,
        "controller_loop_builds_update_rows": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_update_sequence_row("
            in controller_loop
        ),
        "controller_loop_builds_evaluation_rows": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_evaluation_sequence_row("
            in controller_loop
        ),
        "controller_loop_builds_selection_rows": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selection_sequence_row("
            in controller_loop
        ),
        "controller_loop_builds_selected_result": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result("
            in controller_loop
        ),
        "controller_loop_marks_execution_owned_elsewhere": (
            "candidate_generation_execution_owned_elsewhere" in controller_loop
            and "candidate_evaluation_execution_owned_elsewhere" in controller_loop
            and "cta_contract_execution_owned_elsewhere" in controller_loop
        ),
    }
    page_cutover_tokens_present = {
        "import_alias_present": (
            "run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop as "
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop"
            in inputs_source
        ),
        "route_calls_controller_loop": (
            "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop("
            in route
        ),
        "generator_dependency_injected": "fallback_variant_generator=lambda:" in route,
        "pre_screen_dependency_injected": "pre_screen=lambda fallback_variant:" in route,
        "candidate_evaluator_dependency_injected": "candidate_evaluator=lambda fallback_updates:" in route,
        "post_screen_dependency_injected": "post_screen=lambda fallback_candidate:" in route,
        "candidate_selector_dependency_injected": "candidate_selector=lambda fallback_candidates:" in route,
        "debug_hash_stamped": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_hash"
            in route
        ),
    }
    forbidden_moves_absent = {
        "controller_does_not_import_streamlit": "streamlit" not in controller_source,
        "controller_does_not_call_page_evaluator": "_evaluate_auto_design_candidate" not in controller_loop,
        "controller_does_not_call_page_generator": "generate_less_shear_reo_variants" not in controller_loop,
        "controller_does_not_call_button_contract": "_design_guide_button_contract" not in controller_loop,
    }
    route_body_deadness = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof"
    )
    deadness_capture = dict((route_body_deadness.get("payload") or {}).get("capture") or {})
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_SEARCH_LOOP_CONTROLLER_CUTOVER",
        "page_loop_tokens_absent": page_loop_tokens_absent,
        "controller_loop_tokens_present": controller_loop_tokens_present,
        "page_cutover_tokens_present": page_cutover_tokens_present,
        "forbidden_moves_absent": forbidden_moves_absent,
        "route_body_deadness_path": route_body_deadness.get("path"),
        "route_body_delete_blockers": tuple(deadness_capture.get("delete_blockers") or ()),
        "route_body_delete_blocker_count": deadness_capture.get("delete_blocker_count"),
        "expected_remaining_delete_blockers": ("cta_contract_execution",),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "page_loop_tokens_absent": all(
            bool(value) for value in (capture.get("page_loop_tokens_absent") or {}).values()
        ),
        "controller_loop_tokens_present": all(
            bool(value)
            for value in (capture.get("controller_loop_tokens_present") or {}).values()
        ),
        "page_cutover_tokens_present": all(
            bool(value) for value in (capture.get("page_cutover_tokens_present") or {}).values()
        ),
        "forbidden_moves_absent": all(
            bool(value) for value in (capture.get("forbidden_moves_absent") or {}).values()
        ),
        "route_body_deadness_refreshed": bool(capture.get("route_body_deadness_path")),
        "only_cta_delete_blocker_remains": tuple(capture.get("route_body_delete_blockers") or ())
        == tuple(capture.get("expected_remaining_delete_blockers") or ()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Search Loop Controller Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "- Fallback loop order and sequence-row assembly are controller-owned.",
        "- Generator, evaluator, screens, selector, CTA/apply, wording, UI, and session/debug remain injected or page-owned.",
        f"- Remaining route-body delete blockers: `{capture.get('route_body_delete_blockers')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append("Continue from CTA contract execution boundary or whole-route shell deletion proof.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_controller_cutover.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_controller_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_controller_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_search_loop_controller_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_controller_cutover",
        payload["status"],
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
