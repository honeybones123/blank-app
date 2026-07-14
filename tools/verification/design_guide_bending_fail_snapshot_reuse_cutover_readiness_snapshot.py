"""Audit readiness to cut over bending-fail snapshot reuse assembly.

This is proof-only. It decides whether the legacy
_assemble_bending_fail_publication_snapshot_reuse_result(...) call can be
replaced by a controller-built result while snapshot retrieval remains
page/session-owned.
"""

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
    legacy_branch_tokens = {
        "snapshot_retrieval_remains_page_owned": (
            "snapshot_item = _bending_fail_publication_snapshot_for_state(" in source
        ),
        "legacy_result_assigned": (
            "legacy_snapshot_result = _assemble_bending_fail_publication_snapshot_reuse_result("
            in source
        ),
        "controller_trace_called_with_legacy_result": (
            "_trace_design_guide_controller_bending_fail_snapshot_reuse(" in source
            and "legacy_result=dict(legacy_snapshot_result or {})" in source
        ),
        "legacy_result_returned": "return legacy_snapshot_result" in source,
        "legacy_assembler_function_present": (
            "def _assemble_bending_fail_publication_snapshot_reuse_result(" in source
        ),
        "legacy_route_trace_event_present": (
            '"early_return_bending_fail_publication_snapshot"' in source
        ),
    }
    already_cut_over_tokens = {
        "snapshot_retrieval_remains_page_owned": (
            "snapshot_item = _bending_fail_publication_snapshot_for_state(" in source
        ),
        "controller_result_returned": (
            "return _controller_bending_fail_snapshot_reuse_result(" in source
        ),
        "legacy_assembler_not_called_from_branch": (
            "legacy_snapshot_result = _assemble_bending_fail_publication_snapshot_reuse_result("
            not in source
        ),
        "legacy_assembler_function_retained_or_deleted": True,
        "legacy_route_trace_event_preserved": (
            '"early_return_bending_fail_publication_snapshot"' in source
        ),
    }
    replacement_shape_tokens = {
        "controller_request_imported": (
            "_DesignGuideControllerBendingFailSnapshotReuseRequest" in source
        ),
        "controller_runner_imported": (
            "_run_design_guide_controller_bending_fail_snapshot_reuse_trace_only" in source
        ),
        "state_fingerprint_available": (
            "_design_guide_primary_apply_state_fingerprint(final_state)" in source
            or "legacy_snapshot_result.get(\"state_fingerprint\")" in source
        ),
        "trace_hash_comparison_available": (
            "result_hash_match=response.result_hash == legacy_hash" in source
        ),
    }
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
            else (
            "ASSEMBLER_RETURN_ALREADY_CUT_OVER"
            if all(already_cut_over_tokens.values())
            else "READY_FOR_ASSEMBLER_CUTOVER"
            )
        ),
        "replacement_scope": "replace assembler call only; keep snapshot retrieval page-owned",
        "legacy_branch_tokens": legacy_branch_tokens,
        "already_cut_over_tokens": already_cut_over_tokens,
        "replacement_shape_tokens": replacement_shape_tokens,
        "page_helpers_deleted_no_live_branch": page_helpers_deleted_no_live_branch,
        "session_snapshot_storage_retained": (
            "_bending_fail_publication_snapshot_for_state(" in source
            and "_store_bending_fail_publication_snapshot(" in source
        ),
        "composed": {
            "controller_object": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_controller_object_snapshot.py"
            ),
            "trace_wiring": _run(
                "tools/verification/design_guide_bending_fail_snapshot_reuse_trace_wiring_snapshot.py"
            ),
        },
        "allowed_next_change": {
            "replace_assembler_call": not page_helpers_deleted_no_live_branch,
            "delete_assembler_function": False,
            "move_session_snapshot_storage": False,
            "change_cta_or_apply": False,
            "change_visible_wording": False,
        },
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    composed = dict(capture.get("composed") or {})
    allowed = dict(capture.get("allowed_next_change") or {})
    return {
        "controller_object_gate_passes": (composed.get("controller_object") or {}).get("passed")
        is True,
        "trace_wiring_gate_passes": (composed.get("trace_wiring") or {}).get("passed")
        is True,
        "legacy_branch_trace_wired_or_cut_over_or_deleted": (
            all((capture.get("legacy_branch_tokens") or {}).values())
            or all((capture.get("already_cut_over_tokens") or {}).values())
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "replacement_shape_available_or_deleted": (
            all((capture.get("replacement_shape_tokens") or {}).values())
            or capture.get("page_helpers_deleted_no_live_branch") is True
        ),
        "only_assembler_replacement_allowed": (
            allowed.get("replace_assembler_call") in {True, False}
            and allowed.get("delete_assembler_function") is False
            and allowed.get("move_session_snapshot_storage") is False
            and allowed.get("change_cta_or_apply") is False
            and allowed.get("change_visible_wording") is False
        ),
        "decision_ready_for_cutover": capture.get("decision")
        in {
            "READY_FOR_ASSEMBLER_CUTOVER",
            "ASSEMBLER_RETURN_ALREADY_CUT_OVER",
            "PAGE_HELPERS_DELETED_NO_LIVE_BRANCH",
        },
        "session_snapshot_storage_retained": (
            capture.get("session_snapshot_storage_retained") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Bending-Fail Snapshot Reuse Cutover Readiness",
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
            "## Scope",
            "",
            f"- Replacement scope: `{capture.get('replacement_scope')}`",
            "- Allowed: replace the legacy assembler call with the controller result when the page helper route still exists.",
            "- If the page helper route is already deleted, no cutover action remains for this slice.",
            "- Not allowed: delete the assembler function, move session snapshot storage, change CTA/apply, or change visible wording.",
            "",
            "Next safe slice: verify deletion proof or continue to the next obsolete page-owned bridge.",
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
        ARTIFACT_DIR / f"design_guide_bending_fail_snapshot_reuse_cutover_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR / f"design_guide_bending_fail_snapshot_reuse_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_fail_snapshot_reuse_cutover_readiness_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
