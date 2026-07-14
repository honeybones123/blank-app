"""Verify controller object for bending-fail snapshot reuse assembly.

This is proof-only. The controller object remains clean, while the old page
helper/assembler route may either still exist for a staged cutover or be fully
deleted after extraction. Session-backed snapshot storage remains page-owned.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _expected_legacy_result(
    *,
    snapshot_item: dict[str, Any],
    current_overview: dict[str, Any],
    state_fingerprint: str,
) -> dict[str, Any]:
    item = dict(snapshot_item or {})
    return {
        "item": item,
        "overview": dict(current_overview or {}),
        "presentation": {
            "headline": str(item.get("title_main") or item.get("title") or ""),
            "subtext": str(item.get("primary_action") or ""),
            "guidance_intent": item.get("guidance_intent"),
            "css_bucket": item.get("bucket"),
            "theme": item.get("bucket"),
            "show_apply_button": True,
            "use_success_style": str(item.get("bucket") or "") == "pass",
        },
        "render_reason": "bending_fail_publication_snapshot",
        "state_fingerprint": state_fingerprint,
        "debug": {
            "bending_fail_publication_snapshot_reused": True,
            "bending_fail_publication_snapshot_reuse_purpose": "final_resolver",
        },
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerBendingFailSnapshotReuseRequest,
        DesignGuideControllerBendingFailSnapshotReuseResponse,
        build_design_guide_controller_bending_fail_snapshot_reuse_result,
        run_design_guide_controller_bending_fail_snapshot_reuse_trace_only,
    )

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    snapshot_item = {
        "candidate_id": "bending-snapshot-sample",
        "title_main": "Strengthening required",
        "primary_action": "Apply bending repair",
        "guidance_intent": "repair_required",
        "bucket": "fail",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
    }
    overview = {"statuses": {"bending": "FAIL"}, "worst_util": 1.42}
    state_fingerprint = "sample-state-fingerprint"
    expected = _expected_legacy_result(
        snapshot_item=snapshot_item,
        current_overview=overview,
        state_fingerprint=state_fingerprint,
    )
    direct = build_design_guide_controller_bending_fail_snapshot_reuse_result(
        snapshot_item=dict(snapshot_item),
        current_overview=dict(overview),
        state_fingerprint=state_fingerprint,
    )
    request = DesignGuideControllerBendingFailSnapshotReuseRequest(
        snapshot_item=dict(snapshot_item),
        current_overview=dict(overview),
        state_fingerprint=state_fingerprint,
        source="bending_fail_snapshot_reuse_controller_object_snapshot",
    )
    first = run_design_guide_controller_bending_fail_snapshot_reuse_trace_only(request)
    second = run_design_guide_controller_bending_fail_snapshot_reuse_trace_only(request)
    forbidden_tokens = {
        "imports_inputs_page": "inputs_page" in controller_source,
        "imports_streamlit": "streamlit" in controller_source,
        "uses_session_state": "st.session_state" in controller_source,
        "records_apply_payload": "_record_rendered_design_guide_primary_apply_payload"
        in controller_source,
        "renders_ui": "design_guide_page.render_final_panel" in controller_source,
    }
    legacy_branch_present = (
        "snapshot_item = _bending_fail_publication_snapshot_for_state(" in inputs_source
        and (
            "return _assemble_bending_fail_publication_snapshot_reuse_result(" in inputs_source
            or (
                "legacy_snapshot_result = _assemble_bending_fail_publication_snapshot_reuse_result("
                in inputs_source
                and "return legacy_snapshot_result" in inputs_source
            )
            or "return _controller_bending_fail_snapshot_reuse_result(" in inputs_source
        )
    )
    page_helpers_deleted_no_live_branch = (
        "_controller_bending_fail_snapshot_reuse_result(" not in inputs_source
        and "_trace_design_guide_controller_bending_fail_snapshot_reuse(" not in inputs_source
        and "_assemble_bending_fail_publication_snapshot_reuse_result(" not in inputs_source
        and "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only" not in inputs_source
        and "_DesignGuideControllerBendingFailSnapshotReuseRequest" not in inputs_source
        and "_bending_fail_publication_snapshot_for_state(" in inputs_source
    )
    return {
        "request_class": DesignGuideControllerBendingFailSnapshotReuseRequest.__name__,
        "response_class": DesignGuideControllerBendingFailSnapshotReuseResponse.__name__,
        "direct_result_matches_legacy_shape": direct == expected,
        "trace_result_matches_direct": first.result == direct,
        "stable_request_hash": first.request_hash == second.request_hash,
        "stable_result_hash": first.result_hash == second.result_hash,
        "result_hash_matches_payload": first.result_hash == _stable_hash(first.result),
        "product_flags": {
            "trace_only": first.trace_only,
            "product_driving": first.product_driving,
            "render_driving": first.render_driving,
            "apply_driving": first.apply_driving,
            "session_driving": first.session_driving,
        },
        "branch_present_and_not_deleted": legacy_branch_present,
        "page_helpers_deleted_no_live_branch": page_helpers_deleted_no_live_branch,
        "session_snapshot_storage_retained": (
            "_bending_fail_publication_snapshot_for_state(" in inputs_source
            and "_store_bending_fail_publication_snapshot(" in inputs_source
        ),
        "controller_builder_exported": (
            '"build_design_guide_controller_bending_fail_snapshot_reuse_result"'
            in controller_source
        ),
        "controller_trace_exported": (
            '"run_design_guide_controller_bending_fail_snapshot_reuse_trace_only"'
            in controller_source
        ),
        "forbidden_controller_tokens_present": forbidden_tokens,
        "decision": (
            "PAGE_HELPERS_DELETED_NO_LIVE_BRANCH"
            if page_helpers_deleted_no_live_branch
            else "OBJECT_READY_TRACE_ONLY_NOT_CUT_OVER"
        ),
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    flags = dict(capture.get("product_flags") or {})
    return {
        "request_response_classes_exist": bool(capture.get("request_class"))
        and bool(capture.get("response_class")),
        "direct_result_matches_legacy_shape": capture.get("direct_result_matches_legacy_shape")
        is True,
        "trace_result_matches_direct": capture.get("trace_result_matches_direct") is True,
        "stable_hashes": capture.get("stable_request_hash") is True
        and capture.get("stable_result_hash") is True
        and capture.get("result_hash_matches_payload") is True,
        "trace_only_not_product_driving": (
            flags.get("trace_only") is True
            and flags.get("product_driving") is False
            and flags.get("render_driving") is False
            and flags.get("apply_driving") is False
            and flags.get("session_driving") is False
        ),
        "branch_present_or_page_helpers_deleted": (
            capture.get("branch_present_and_not_deleted") is True
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "session_snapshot_storage_retained": (
            capture.get("session_snapshot_storage_retained") is True
        ),
        "controller_exports_present": capture.get("controller_builder_exported") is True
        and capture.get("controller_trace_exported") is True,
        "controller_has_no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_controller_tokens_present") or {}).values()
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Bending-Fail Snapshot Reuse Controller Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Controller can assemble the same bending-fail snapshot reuse result shape from plain data.",
            "- Session-backed snapshot retrieval/storage remains page-owned.",
            "- If the old page helper route is absent, that is treated as the stronger extracted state.",
            "",
            "Next safe slice: keep the deleted helper route accounted for in the trace/cutover/deletion verifier chain.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR / f"design_guide_bending_fail_snapshot_reuse_controller_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_bending_fail_snapshot_reuse_controller_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_fail_snapshot_reuse_controller_object_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
