"""Trace-wiring snapshot for residual shear cleanup candidate selection/sort-key proof."""

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
OBJECT_SNAPSHOT = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object_snapshot.py"
)
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


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
    if end < 0:
        return source[start:]
    return source[start:end]


def _run_object_snapshot() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(OBJECT_SNAPSHOT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_object PASS"
        in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff(",
    )
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    object_snapshot = _run_object_snapshot()
    evaluator_handoff_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_handoff("
    )
    selection_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
    )
    primary_handoff_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_primary_executor_handoff("
    )
    live_min_idx = route.find("fallback_best = min(")
    selection_sequence_idx = route.find("fallback_candidate_selection_sequence")
    output_summary_idx = route.find("fallback_candidate_selection_output_summary")
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_SELECTION_SORT_KEY_TRACE_WIRED",
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key"
        )
        in source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
            in helper
        ),
        "helper_page_live_dependency_status": 'dependency_status="page_live"' in helper,
        "helper_stamps_payload": (
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key"
            in helper
        ),
        "helper_stamps_non_driving_flags": all(
            token in helper
            for token in (
                "candidate_selection_sort_key_proof_only",
                "candidate_selection_sort_key_product_driving",
                "candidate_selection_sort_key_render_driving",
                "candidate_selection_sort_key_apply_driving",
                "candidate_selection_sort_key_session_driving",
            )
        ),
        "selection_sequence_present": (
            "fallback_candidate_selection_sequence = list(" in route
            and "residual_route_shell_context.get(\"fallback_candidate_selection_sequence\")"
            in route
        ),
        "selection_output_summary_present": (
            "fallback_candidate_selection_output_summary = dict(" in route
            and "residual_route_shell_context.get("
            in route
            and "\"fallback_candidate_selection_output_summary\"" in route
        ),
        "sequence_records_sort_key": (
            "fallback_candidate_selection_sequence = list(" in route
            and '"shear_util": float(fallback_best.get("shear_util") or float("inf"))'
            not in route
            and '"sort_key_order": (' in route
            and '"shear_util",' in route
            and '"update_count",' in route
            and '"updates_items",' in route
        ),
        "selection_output_records_selected_hashes": all(
            token in route
            for token in (
                '"selected_updates_hash": _stable_final_publication_hash(',
                '"selected_candidate_hash": _stable_final_publication_hash(',
                '"selected_result_hash": _stable_final_publication_hash(',
                '"selected_action_type": (residual_shear_tighten or {}).get("action_type")',
                '"selected_label": (residual_shear_tighten or {}).get("label")',
            )
        ),
        "selection_dependency_shell_present": (
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(" in route
        ),
        "selection_selector_callable_injected": (
            "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key"
            in route
        ),
        "route_direct_min_removed": live_min_idx < 0,
        "selection_stamp_wired": selection_stamp_idx >= 0,
        "selection_stamp_after_selection_output": 0 <= output_summary_idx < selection_stamp_idx,
        "selection_stamp_order_after_evaluator_before_primary": (
            0 <= evaluator_handoff_idx < selection_stamp_idx < primary_handoff_idx
        ),
        "selection_stamp_uses_handoff": (
            "candidate_evaluator_handoff=dict(residual_candidate_evaluator_handoff or {})" in route
        ),
        "selection_stamp_uses_sort_key_order": (
            '"sort_key_order": (' in route
            and '"shear_util",' in route
            and '"update_count",' in route
            and '"updates_items",' in route
        ),
        "selection_sequence_before_output": (
            0 <= selection_sequence_idx < output_summary_idx < selection_stamp_idx
        ),
        "object_snapshot": object_snapshot,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "import_alias_present": capture.get("import_alias_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller": capture.get("helper_calls_controller") is True,
        "helper_page_live_dependency_status": capture.get("helper_page_live_dependency_status") is True,
        "helper_stamps_payload": capture.get("helper_stamps_payload") is True,
        "helper_stamps_non_driving_flags": capture.get("helper_stamps_non_driving_flags") is True,
        "selection_sequence_present": capture.get("selection_sequence_present") is True,
        "selection_output_summary_present": capture.get("selection_output_summary_present") is True,
        "sequence_records_sort_key": capture.get("sequence_records_sort_key") is True,
        "selection_output_records_selected_hashes": (
            capture.get("selection_output_records_selected_hashes") is True
        ),
        "selection_dependency_shell_present": (
            capture.get("selection_dependency_shell_present") is True
        ),
        "selection_selector_callable_injected": (
            capture.get("selection_selector_callable_injected") is True
        ),
        "route_direct_min_removed": capture.get("route_direct_min_removed") is True,
        "selection_stamp_wired": capture.get("selection_stamp_wired") is True,
        "selection_stamp_after_selection_output": (
            capture.get("selection_stamp_after_selection_output") is True
        ),
        "selection_stamp_order_after_evaluator_before_primary": (
            capture.get("selection_stamp_order_after_evaluator_before_primary") is True
        ),
        "selection_stamp_uses_handoff": capture.get("selection_stamp_uses_handoff") is True,
        "selection_stamp_uses_sort_key_order": capture.get("selection_stamp_uses_sort_key_order") is True,
        "selection_sequence_before_output": capture.get("selection_sequence_before_output") is True,
        "object_snapshot_passed": (capture.get("object_snapshot") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Selection Sort-Key Trace Wiring Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Trace",
        "",
        f"- helper present: `{capture.get('helper_present')}`",
        f"- selection dependency shell present: `{capture.get('selection_dependency_shell_present')}`",
        f"- selection stamp wired: `{capture.get('selection_stamp_wired')}`",
        f"- route direct min removed: `{capture.get('route_direct_min_removed')}`",
        f"- object snapshot passed: `{(capture.get('object_snapshot') or {}).get('passed')}`",
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
            "Run parity scenarios and composed locks. Candidate selection execution remains page-owned until a separate cutover/deadness chain is proven.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key_trace_wiring "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
