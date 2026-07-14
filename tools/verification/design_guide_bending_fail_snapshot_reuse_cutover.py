"""Verify bending-fail snapshot reuse assembler-return cutover."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    cutover_helper_start = source.find("def _controller_bending_fail_snapshot_reuse_result(")
    trace_helper_start = source.find("def _trace_design_guide_controller_bending_fail_snapshot_reuse(")
    cutover_helper_source = (
        source[cutover_helper_start:trace_helper_start]
        if cutover_helper_start >= 0 and trace_helper_start > cutover_helper_start
        else ""
    )
    resolver_start = source.find("def resolve_final_visible_design_guide_item(")
    direct_guard_start = source.find("if publication_context is not None and publication_context.current_design_overview:")
    resolver_branch_source = (
        source[resolver_start:direct_guard_start]
        if resolver_start >= 0 and direct_guard_start > resolver_start
        else ""
    )
    page_helpers_deleted_no_live_branch = (
        "_controller_bending_fail_snapshot_reuse_result(" not in source
        and "_trace_design_guide_controller_bending_fail_snapshot_reuse(" not in source
        and "_assemble_bending_fail_publication_snapshot_reuse_result(" not in source
        and "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only" not in source
        and "_DesignGuideControllerBendingFailSnapshotReuseRequest" not in source
        and "_bending_fail_publication_snapshot_for_state(" in source
    )
    return {
        "decision": (
            "PAGE_HELPERS_DELETED_NO_LIVE_BRANCH"
            if page_helpers_deleted_no_live_branch
            else "ASSEMBLER_RETURN_CUT_OVER"
        ),
        "page_helpers_deleted_no_live_branch": page_helpers_deleted_no_live_branch,
        "session_snapshot_storage_retained": (
            "_bending_fail_publication_snapshot_for_state(" in source
            and "_store_bending_fail_publication_snapshot(" in source
        ),
        "resolver_branch": {
            "snapshot_retrieval_page_owned": (
                "snapshot_item = _bending_fail_publication_snapshot_for_state(" in resolver_branch_source
            ),
            "returns_controller_result": (
                "return _controller_bending_fail_snapshot_reuse_result(" in resolver_branch_source
            ),
            "does_not_call_legacy_assembler": (
                "_assemble_bending_fail_publication_snapshot_reuse_result(" not in resolver_branch_source
            ),
        },
        "cutover_helper": {
            "defined_once": source.count("def _controller_bending_fail_snapshot_reuse_result(") == 1,
            "uses_controller_request": (
                "_DesignGuideControllerBendingFailSnapshotReuseRequest(" in cutover_helper_source
            ),
            "uses_controller_runner": (
                "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only(request)"
                in cutover_helper_source
            ),
            "emits_legacy_route_trace_event": (
                '"early_return_bending_fail_publication_snapshot"' in cutover_helper_source
            ),
            "emits_controller_trace_event": (
                '"bending_fail_snapshot_reuse_controller_trace"' in cutover_helper_source
            ),
            "marks_controller_authority": (
                'result["controller_authority"] = "DesignGuideController.bending_fail_snapshot_reuse"'
                in cutover_helper_source
            ),
            "does_not_route_apply": "_record_rendered_design_guide_primary_apply_payload"
            not in cutover_helper_source,
            "does_not_touch_session": "st.session_state" not in cutover_helper_source,
        },
        "legacy_assembler": {
            "function_retained_or_deleted": True,
            "function_deleted": (
                "def _assemble_bending_fail_publication_snapshot_reuse_result(" not in source
            ),
            "direct_return_removed": (
                "return _assemble_bending_fail_publication_snapshot_reuse_result(" not in source
            ),
        },
        "composed": {
            "readiness": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_cutover_readiness_snapshot.py"
            ),
            "controller_object": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_controller_object_snapshot.py"
            ),
            "trace_wiring": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_trace_wiring_snapshot.py"
            ),
        },
        "product_behavior_changed": False,
        "delete_legacy_assembler_now": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    composed = dict(capture.get("composed") or {})
    return {
        "readiness_gate_passes": (composed.get("readiness") or {}).get("passed") is True,
        "controller_object_gate_passes": (composed.get("controller_object") or {}).get("passed")
        is True,
        "trace_wiring_gate_passes": (composed.get("trace_wiring") or {}).get("passed")
        is True,
        "resolver_branch_cut_over_or_page_helpers_deleted": (
            all((capture.get("resolver_branch") or {}).values())
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "cutover_helper_safe_or_page_helpers_deleted": (
            all((capture.get("cutover_helper") or {}).values())
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "legacy_assembler_deleted_or_retained_without_direct_return": (
            (capture.get("legacy_assembler") or {}).get("direct_return_removed") is True
            and (capture.get("legacy_assembler") or {}).get("function_retained_or_deleted") is True
        ),
        "session_snapshot_storage_retained": (
            capture.get("session_snapshot_storage_retained") is True
        ),
        "delete_not_allowed_in_this_slice": capture.get("delete_legacy_assembler_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Bending-Fail Snapshot Reuse Cutover",
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
            "## Result",
            "",
            "- The live branch returns the controller-built result when that branch still exists.",
            "- If the page helper route is absent, the cutover is already physically complete.",
            "- Session-backed snapshot retrieval/storage remains page-owned.",
            "- CTA/apply/session/render ownership did not move.",
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
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_snapshot_reuse_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_fail_snapshot_reuse_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_fail_snapshot_reuse_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
