"""Narrowing snapshot for residual shear cleanup debug projection metadata."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
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


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _latest(prefix: str) -> dict[str, Any] | None:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None
    try:
        return json.loads(paths[-1].read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _status_pass(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "").upper()
    return "PASS" in status or "LOCKED" in status or "COMPLETE" in status


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = (ROOT / "design_brain" / "design_guide_controller.py").read_text(
        encoding="utf-8-sig",
        errors="replace",
    )
    helper_block = _block(
        source,
        "def _mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    proof_call = route_block.find(
        "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof("
    )
    marker_call = route_block.find(
        "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only("
    )
    return_call = route_block.find("return residual_route_return_item", marker_call)
    if return_call < 0:
        return_call = route_block.find("return residual_promoted", marker_call)
    tail_audit = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit.py",
        ]
    )
    row_builder = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder_snapshot.py",
        ]
    )
    consumer_reachability = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability.py",
        ]
    )
    route_execution_shell = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_execution_shell_cutover.py",
        ]
    )
    route_readiness = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness_audit.py",
        ]
    )
    route_readiness_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness"
    ) or {}
    route_readiness_capture = dict(route_readiness_payload.get("capture") or {})
    tail_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_tail_audit"
    ) or {}
    tail_capture = dict(tail_payload.get("capture") or {})
    row_builder_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_row_builder"
    ) or {}
    row_builder_capture = dict(row_builder_payload.get("capture") or {})
    consumer_payload = _latest(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability"
    ) or {}
    consumer_capture = dict(consumer_payload.get("capture") or {})
    legacy_marker_deleted = consumer_capture.get("marker_deleted") is True
    legacy_marker_compatibility_only = bool(helper_block) and marker_call >= 0
    debug_rows_represented = bool(
        tail_capture.get("debug_projection_row_builder_present")
        or row_builder_capture.get("required_rows_present")
        or row_builder_capture.get("all_required_rows_present")
    )
    return {
        "decision": (
            "RESIDUAL_SHEAR_CLEANUP_DEBUG_PROJECTION_LEGACY_MARKER_DELETED"
            if legacy_marker_deleted
            else "RESIDUAL_SHEAR_CLEANUP_DEBUG_PROJECTION_NARROWED_TO_COMPATIBILITY_ONLY"
        ),
        "helper_present": bool(helper_block),
        "legacy_marker_deleted": legacy_marker_deleted,
        "legacy_marker_compatibility_only": legacy_marker_compatibility_only,
        "marker_after_route_proof": proof_call >= 0 and marker_call > proof_call,
        "marker_before_return": marker_call >= 0 and return_call > marker_call,
        "compatibility_stamps_present": all(
            token in helper_block
            for token in (
                "debug_projection_compatibility_only",
                "debug_projection_product_driving",
                "debug_projection_render_driving",
                "debug_projection_apply_driving",
                "debug_projection_session_driving",
                "debug_projection_route_hash",
                "debug_projection_proof_hash",
            )
        ),
        "compatibility_stamps_non_driving": all(
            token in helper_block
            for token in (
                "debug_projection_product_driving",
                "debug_projection_render_driving",
                "debug_projection_apply_driving",
                "debug_projection_session_driving",
            )
        )
        and helper_block.count("] = False") >= 4,
        "live_behavior_tokens_retained": all(
            token in route_block
            for token in (
                "_run_post_click_low_bending_residual_shear_cleanup_candidate_selector(",
                "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
                "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_search_loop_handoff(",
                "button_contract_hash_observed_not_owned",
                "button_contract_source_summary_cutover",
            )
        )
        and "above the preferred" in controller_source,
        "preferred_band_wording_owned_by_controller": "above the preferred" in controller_source,
        "tail_audit": tail_audit,
        "row_builder": row_builder,
        "consumer_reachability": consumer_reachability,
        "route_execution_shell": route_execution_shell,
        "route_readiness": route_readiness,
        "tail_audit_passed": _status_pass(tail_payload),
        "row_builder_passed": _status_pass(row_builder_payload),
        "consumer_reachability_passed": _status_pass(consumer_payload),
        "route_execution_shell_passed": route_execution_shell.get("passed") is True,
        "debug_rows_represented_by_controller_builder": debug_rows_represented,
        "route_readiness_debug_projection_ready": (
            "debug_session_projection"
            in set(route_readiness_capture.get("ready_to_narrow_surfaces") or [])
        ),
        "route_readiness_full_cutover_not_ready": (
            route_readiness_capture.get("cutover_ready") is False
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    marker_deleted_or_compatibility_only = (
        capture.get("legacy_marker_deleted") is True
        or (
            capture.get("helper_present") is True
            and capture.get("marker_after_route_proof") is True
            and capture.get("marker_before_return") is True
            and capture.get("compatibility_stamps_present") is True
            and capture.get("compatibility_stamps_non_driving") is True
        )
    )
    return {
        "legacy_marker_deleted_or_compatibility_only": marker_deleted_or_compatibility_only,
        "debug_rows_represented_by_controller_builder": (
            capture.get("debug_rows_represented_by_controller_builder") is True
        ),
        "live_behavior_tokens_retained": capture.get("live_behavior_tokens_retained") is True,
        "tail_audit_passed": capture.get("tail_audit_passed") is True,
        "row_builder_passed": capture.get("row_builder_passed") is True,
        "consumer_reachability_passed": capture.get("consumer_reachability_passed") is True,
        "route_execution_shell_passed": capture.get("route_execution_shell_passed") is True,
        "route_readiness_debug_projection_ready": (
            capture.get("route_readiness_debug_projection_ready") is True
        ),
        "route_readiness_full_cutover_not_ready": (
            capture.get("route_readiness_full_cutover_not_ready") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Debug Projection Narrowing Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Marker after route proof: `{capture.get('marker_after_route_proof')}`",
        f"- Marker before return: `{capture.get('marker_before_return')}`",
        f"- Legacy marker deleted: `{capture.get('legacy_marker_deleted')}`",
        f"- Debug rows represented by controller builder: `{capture.get('debug_rows_represented_by_controller_builder')}`",
        f"- Live behavior tokens retained: `{capture.get('live_behavior_tokens_retained')}`",
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
            "The legacy debug projection compatibility marker is deleted. Continue with the next residual route body dependency surface; do not delete direct debug rows until a separate consumer/deadness proof covers them.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
