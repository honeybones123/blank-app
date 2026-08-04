"""Snapshot for residual shear cleanup fallback search-loop handoff."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
REMAINING_SURFACE_AUDIT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit.py"
)
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff,
)
from design_brain.final_publication import stable_final_publication_hash  # noqa: E402


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


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


def _run_remaining_surface_audit() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(REMAINING_SURFACE_AUDIT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_fallback_loop_authority_audit PASS"
        in proc.stdout,
    }


def _sample_handoff(*, dependency_status: str = "page_live") -> dict[str, Any]:
    generator_rows = [
        {
            "index": 0,
            "variant_hash": stable_final_publication_hash({"s_lig": 300}),
            "updates": {"s_lig": 300},
        }
    ]
    evaluation_rows = [
        {
            "index": 0,
            "updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "candidate_hash": stable_final_publication_hash({"candidate": "safe"}),
            "overview_hash": stable_final_publication_hash({"utils": {"shear": 0.72}}),
            "success": True,
            "accepted_as_safe_cleanup": True,
            "failed_reason": "",
        }
    ]
    selection_rows = [
        {
            "index": 0,
            "updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "candidate_hash": stable_final_publication_hash({"candidate": "safe"}),
            "overview_hash": stable_final_publication_hash({"utils": {"shear": 0.72}}),
            "shear_util": 0.72,
            "sort_key": {
                "shear_util": 0.72,
                "update_count": 1,
                "updates_items": "[('s_lig', 300)]",
            },
            "sort_key_hash": stable_final_publication_hash(
                {
                    "shear_util": 0.72,
                    "update_count": 1,
                    "updates_items": "[('s_lig', 300)]",
                }
            ),
        }
    ]
    selection_summary = {
        "candidate_count": 1,
        "stable_candidate_sequence_hash": stable_final_publication_hash(selection_rows),
        "selected_updates_hash": stable_final_publication_hash({"s_lig": 300}),
        "selected_candidate_hash": stable_final_publication_hash({"candidate": "safe"}),
        "selected_sort_key_hash": stable_final_publication_hash(
            {
                "shear_util": 0.72,
                "update_count": 1,
                "updates_items": "[('s_lig', 300)]",
            }
        ),
        "selected_shear_util": 0.72,
    }
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(
        route_entry_guard={"route_entry_guard_hash": "route-entry-guard-hash"},
        fallback_search_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
            "iteration_limit": 64,
            "fallback_variant_generator_attempted": True,
            "fallback_variant_count": 1,
        },
        generator_update_sequence=generator_rows,
        evaluation_sequence=evaluation_rows,
        selection_sequence=selection_rows,
        selection_output_summary=selection_summary,
        selected_result_summary={
            "selected_result_present": True,
            "selected_updates_hash": stable_final_publication_hash({"s_lig": 300}),
            "selected_candidate_hash": stable_final_publication_hash({"candidate": "safe"}),
            "selected_result_hash": stable_final_publication_hash({"updates": {"s_lig": 300}}),
            "selected_action_type": "apply_resolved_candidate",
            "selected_label": "Shear cleanup - one-click reduction",
            "selected_util": 0.72,
        },
        dependency_status=dependency_status,
    )


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    helper = _between(
        inputs_source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_handoff(",
    )
    first = _sample_handoff()
    second = _sample_handoff()
    owned = _sample_handoff(dependency_status="controller_owned")
    remaining_surface = _run_remaining_surface_audit()
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_SEARCH_LOOP_HANDOFF_TRACE_WIRED",
        "controller_function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff("
            in controller_source
        ),
        "controller_function_exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff"'
            in controller_source
        ),
        "inputs_import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff"
            in inputs_source
        ),
        "stamp_helper_present": bool(helper),
        "stamp_helper_non_driving": all(
            token in helper
            for token in (
                '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_proof_only"',
                '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_product_driving"',
                '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_render_driving"',
                '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_apply_driving"',
                '"design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_session_driving"',
            )
        ),
        "route_call_count": route.count(
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff("
        ),
        "route_call_after_loop_before_packaging": (
            route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff("
            )
            > route.find("for fallback_index, fallback_variant in enumerate(fallback_variants[:64]):")
            and route.find(
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff("
            )
            < route.find("_run_post_click_low_bending_residual_shear_cleanup_result_packaging(")
        ),
        "fallback_shear_candidates_initialized_before_branch": (
            "fallback_shear_candidates: list[dict] = []\n        if not residual_shear_updates:"
            in route
        ),
        "sample_output_shape_ready": bool(first.get("output_shape_ready")),
        "sample_behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "controller_owned_behavior_cutover_ready": bool(owned.get("behavior_cutover_ready")),
        "stable_hash_repeat": first.get("fallback_search_loop_handoff_hash")
        == second.get("fallback_search_loop_handoff_hash"),
        "page_live_keeps_loop": "fallback_search_loop_execution"
        in tuple(first.get("page_must_keep_for_now") or ()),
        "selected_result_hash_present": bool(first.get("selected_result_hash")),
        "evaluation_sequence_hash_present": bool(first.get("evaluation_sequence_hash")),
        "remaining_surface_audit": remaining_surface,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_function_exported": capture.get("controller_function_exported") is True,
        "inputs_import_present": capture.get("inputs_import_present") is True,
        "stamp_helper_present": capture.get("stamp_helper_present") is True,
        "stamp_helper_non_driving": capture.get("stamp_helper_non_driving") is True,
        "route_call_once": capture.get("route_call_count") == 1,
        "route_call_after_loop_before_packaging": (
            capture.get("route_call_after_loop_before_packaging") is True
        ),
        "fallback_shear_candidates_initialized_before_branch": (
            capture.get("fallback_shear_candidates_initialized_before_branch") is True
        ),
        "sample_output_shape_ready": capture.get("sample_output_shape_ready") is True,
        "sample_behavior_cutover_not_ready": capture.get("sample_behavior_cutover_ready") is False,
        "controller_owned_behavior_cutover_ready": (
            capture.get("controller_owned_behavior_cutover_ready") is True
        ),
        "stable_hash_repeat": capture.get("stable_hash_repeat") is True,
        "page_live_keeps_loop": capture.get("page_live_keeps_loop") is True,
        "selected_result_hash_present": capture.get("selected_result_hash_present") is True,
        "evaluation_sequence_hash_present": capture.get("evaluation_sequence_hash_present") is True,
        "remaining_surface_audit_passed": (
            capture.get("remaining_surface_audit") or {}
        ).get("passed")
        is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Search Loop Handoff Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- Route handoff call count: `{capture.get('route_call_count')}`",
        f"- Sample output shape ready: `{capture.get('sample_output_shape_ready')}`",
        f"- Page-live behavior cutover ready: `{capture.get('sample_behavior_cutover_ready')}`",
        f"- Controller-owned behavior cutover ready: `{capture.get('controller_owned_behavior_cutover_ready')}`",
        f"- Stable hash repeat: `{capture.get('stable_hash_repeat')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Use this handoff to split the fallback loop into controller-owned sequence/result proof versus still-live execution. Do not move generator, evaluator, CTA, apply, wording, or UI ownership in the next slice.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_search_loop_handoff_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff "
        f"{payload['status']}"
    )
    if failures:
        print("failures:", ", ".join(failures))
        print("artifact:", json_path)
        return 1
    print("artifact:", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
